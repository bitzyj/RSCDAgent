#!/usr/bin/env python3
"""
circuit_breaker.py - 熔断与容灾模块

提供：
- 超时控制
- 自动重试
- 回滚机制

用法:
    from circuit_breaker import CircuitBreaker, RetryPolicy, RollbackManager
"""

import time
import traceback
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Tuple


class CircuitState(Enum):
    CLOSED = "closed"      # 正常
    OPEN = "open"          # 熔断
    HALF_OPEN = "half_open"  # 半开


@dataclass
class RetryPolicy:
    """重试策略"""
    max_attempts: int = 3
    initial_delay: float = 1.0  # 秒
    max_delay: float = 60.0
    exponential_backoff: bool = True
    retry_on_timeout: bool = True


@dataclass
class RollbackAction:
    """回滚操作"""
    action_id: str
    action_type: str  # "file_modify", "config_change", "env_create"
    target: str
    original_state: str
    rollback_command: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CircuitBreakerResult:
    """熔断器执行结果"""
    success: bool
    result: Any = None
    error: Optional[str] = None
    attempts: int = 1
    duration_seconds: float = 0.0
    circuit_state: str = CircuitState.CLOSED.value
    rolled_back: bool = False
    rollback_actions: List[RollbackAction] = field(default_factory=list)


class CircuitBreaker:
    """熔断器"""

    def __init__(self,
                 failure_threshold: int = 5,
                 recovery_timeout: float = 60.0,
                 expected_exception: type = Exception):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self._failure_count = 0
        self._last_failure_time: Optional[datetime] = None
        self._state = CircuitState.CLOSED

    @property
    def state(self) -> CircuitState:
        """获取当前状态"""
        if self._state == CircuitState.OPEN:
            # 检查是否超时恢复
            if self._last_failure_time:
                if datetime.now() - self._last_failure_time > timedelta(seconds=self.recovery_timeout):
                    self._state = CircuitState.HALF_OPEN
        return self._state

    def record_success(self):
        """记录成功"""
        self._failure_count = 0
        self._state = CircuitState.CLOSED

    def record_failure(self):
        """记录失败"""
        self._failure_count += 1
        self._last_failure_time = datetime.now()

        if self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN

    def execute(self, func: Callable, *args, **kwargs) -> CircuitBreakerResult:
        """执行带熔断保护的函数"""
        start_time = time.time()

        if self.state == CircuitState.OPEN:
            return CircuitBreakerResult(
                success=False,
                error="Circuit breaker is OPEN",
                duration_seconds=time.time() - start_time,
                circuit_state=self.state.value
            )

        try:
            result = func(*args, **kwargs)
            self.record_success()
            return CircuitBreakerResult(
                success=True,
                result=result,
                duration_seconds=time.time() - start_time,
                circuit_state=self.state.value
            )
        except self.expected_exception as e:
            self.record_failure()
            return CircuitBreakerResult(
                success=False,
                error=str(e),
                duration_seconds=time.time() - start_time,
                circuit_state=self.state.value
            )


class RetryableExecutor:
    """可重试执行器"""

    def __init__(self, policy: RetryPolicy = None):
        self.policy = policy or RetryPolicy()

    def execute(self, func: Callable, *args,
                on_retry: Callable[[int, Exception], None] = None,
                **kwargs) -> CircuitBreakerResult:
        """执行带重试的函数"""
        start_time = time.time()
        last_error: Optional[Exception] = None
        delay = self.policy.initial_delay

        for attempt in range(1, self.policy.max_attempts + 1):
            try:
                result = func(*args, **kwargs)
                return CircuitBreakerResult(
                    success=True,
                    result=result,
                    attempts=attempt,
                    duration_seconds=time.time() - start_time
                )
            except Exception as e:
                last_error = e

                # 检查是否应该重试
                if not self._should_retry(e, attempt):
                    return CircuitBreakerResult(
                        success=False,
                        error=str(e),
                        attempts=attempt,
                        duration_seconds=time.time() - start_time
                    )

                # 调用重试回调
                if on_retry:
                    on_retry(attempt, e)

                # 等待后重试
                if attempt < self.policy.max_attempts:
                    time.sleep(delay)

                    # 指数退避
                    if self.policy.exponential_backoff:
                        delay = min(delay * 2, self.policy.max_delay)

        # 所有重试都失败
        return CircuitBreakerResult(
            success=False,
            error=str(last_error),
            attempts=self.policy.max_attempts,
            duration_seconds=time.time() - start_time
        )

    def _should_retry(self, exception: Exception, attempt: int) -> bool:
        """判断是否应该重试"""
        if attempt >= self.policy.max_attempts:
            return False

        # 超时错误通常值得重试
        if self.policy.retry_on_timeout:
            error_str = str(exception).lower()
            if "timeout" in error_str or "timed out" in error_str:
                return True

        # 其他错误默认重试
        return True


class RollbackManager:
    """回滚管理器"""

    def __init__(self):
        self._actions: List[RollbackAction] = []
        self._lock_manager = None  # 可以扩展为文件锁管理

    def record_action(self, action_type: str, target: str,
                     original_state: str, rollback_command: str) -> str:
        """记录需要回滚的操作"""
        action_id = str(uuid.uuid4())[:8]
        action = RollbackAction(
            action_id=action_id,
            action_type=action_type,
            target=target,
            original_state=original_state,
            rollback_command=rollback_command
        )
        self._actions.append(action)
        return action_id

    def remove_action(self, action_id: str):
        """移除已回滚的操作"""
        self._actions = [a for a in self._actions if a.action_id != action_id]

    def rollback_all(self) -> List[Tuple[bool, str]]:
        """执行所有回滚操作（逆序）"""
        results = []
        for action in reversed(self._actions):
            success, message = self._execute_rollback(action)
            results.append((success, message))
            if success:
                self.remove_action(action.action_id)
        return results

    def rollback_to(self, action_id: str) -> List[Tuple[bool, str]]:
        """回滚到指定操作"""
        # 找到目标操作的索引
        target_index = -1
        for i, action in enumerate(self._actions):
            if action.action_id == action_id:
                target_index = i
                break

        if target_index == -1:
            return [(False, f"Action {action_id} not found")]

        # 回滚到该操作为止
        results = []
        for action in reversed(self._actions[:target_index + 1]):
            success, message = self._execute_rollback(action)
            results.append((success, message))
            if success:
                self.remove_action(action.action_id)

        return results

    def _execute_rollback(self, action: RollbackAction) -> Tuple[bool, str]:
        """执行单个回滚操作"""
        try:
            import subprocess

            if action.action_type == "file_modify":
                # 回滚文件修改
                with open(action.target, "w", encoding="utf-8") as f:
                    f.write(action.original_state)
                return (True, f"Rolled back file: {action.target}")

            elif action.action_type == "config_change":
                # 回滚配置更改
                result = subprocess.run(
                    action.rollback_command,
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return (True, f"Rolled back config: {action.target}")
                else:
                    return (False, f"Rollback failed: {result.stderr}")

            elif action.action_type == "env_create":
                # 回滚环境创建（删除）
                result = subprocess.run(
                    f"conda env remove -n {action.target}",
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return (True, f"Removed environment: {action.target}")
                else:
                    return (False, f"Environment removal failed: {result.stderr}")

            else:
                # 执行自定义回滚命令
                result = subprocess.run(
                    action.rollback_command,
                    shell=True,
                    capture_output=True,
                    text=True
                )
                if result.returncode == 0:
                    return (True, f"Rollback success: {action.target}")
                else:
                    return (False, f"Rollback failed: {result.stderr}")

        except Exception as e:
            return (False, f"Rollback error: {str(e)}")

    def get_pending_actions(self) -> List[Dict]:
        """获取待回滚操作列表"""
        return [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "target": a.target,
                "timestamp": a.timestamp
            }
            for a in self._actions
        ]


def with_timeout(func: Callable, timeout_seconds: float, *args, **kwargs) -> Any:
    """带超时执行的包装器"""
    import signal

    def timeout_handler(signum, frame):
        raise TimeoutError(f"Function {func.__name__} timed out after {timeout_seconds}s")

    # 设置超时信号
    old_handler = signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(int(timeout_seconds))

    try:
        result = func(*args, **kwargs)
        return result
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, old_handler)


# CLI 测试
if __name__ == "__main__":
    # 测试熔断器
    print("=" * 50)
    print("熔断器测试")
    print("=" * 50)

    cb = CircuitBreaker(failure_threshold=3)

    def flaky_function(should_fail: bool = False):
        if should_fail:
            raise Exception("Simulated failure")
        return "Success"

    # 测试成功
    result = cb.execute(flaky_function, should_fail=False)
    print(f"Success test: {result.success}, state: {result.circuit_state}")

    # 测试失败
    for i in range(3):
        result = cb.execute(flaky_function, should_fail=True)
        print(f"Failure test {i+1}: {result.success}, state: {result.circuit_state}")

    print("\n" + "=" * 50)
    print("重试执行器测试")
    print("=" * 50)

    retry_exec = RetryableExecutor(RetryPolicy(max_attempts=3))

    def unstable_function(fail_count: int = 0):
        def inner():
            if inner.attempts < fail_count:
                raise Exception("Temporary failure")
            return "Success"
        inner.attempts = 0
        return inner

    # 测试重试
    attempt_counter = [0]

    def failing_func():
        attempt_counter[0] += 1
        if attempt_counter[0] < 3:
            raise Exception(f"Attempt {attempt_counter[0]} failed")
        return "Finally succeeded"

    result = retry_exec.execute(failing_func)
    print(f"Retry test: success={result.success}, attempts={result.attempts}")

    print("\n" + "=" * 50)
    print("回滚管理器测试")
    print("=" * 50)

    rm = RollbackManager()

    # 模拟记录操作
    import tempfile
    import os

    # 创建临时文件
    with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
        f.write("original content")
        temp_file = f.name

    original = open(temp_file, 'r').read()
    rm.record_action(
        action_type="file_modify",
        target=temp_file,
        original_state=original,
        rollback_command=f"echo 'rolled back' > {temp_file}"
    )

    print(f"Pending actions: {len(rm.get_pending_actions())}")

    # 执行回滚
    results = rm.rollback_all()
    for success, msg in results:
        print(f"Rollback: {success} - {msg}")

    # 清理
    os.unlink(temp_file)
