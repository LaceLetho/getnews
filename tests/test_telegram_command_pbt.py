"""
属性测试: Telegram命令权限验证一致性

功能: crypto-news-analyzer
属性 18: 命令权限验证一致性

验证: 需求 16.5, 16.10, 16.11

对于任何通过Telegram发送的命令，系统应该验证发送者的权限，
只有授权用户才能触发执行，未授权用户应该收到权限拒绝消息。
"""

import pytest
from hypothesis import given, strategies as st, settings, assume
from datetime import datetime
from typing import List, Dict, Any

from crypto_news_analyzer.models import TelegramCommandConfig
from crypto_news_analyzer.reporters.telegram_command_handler import TelegramCommandHandler


# 策略：生成用户ID
@st.composite
def user_id_strategy(draw):
    """生成Telegram用户ID（正整数字符串）"""
    return str(draw(st.integers(min_value=1, max_value=999999999)))


# 策略：生成用户名
@st.composite
def username_strategy(draw):
    """生成Telegram用户名"""
    return draw(st.text(
        alphabet=st.characters(whitelist_categories=('Lu', 'Ll', 'Nd'), min_codepoint=65, max_codepoint=122),
        min_size=3,
        max_size=20
    ))


# 策略：生成授权用户配置
@st.composite
def authorized_user_config_strategy(draw):
    """生成授权用户配置"""
    user_id = draw(user_id_strategy())
    username = draw(username_strategy())
    
    # 生成权限列表（可能为空，表示所有权限）
    all_permissions = ["run", "status", "help"]
    permissions = draw(st.one_of(
        st.just([]),  # 空列表表示所有权限
        st.lists(st.sampled_from(all_permissions), min_size=1, max_size=3, unique=True)
    ))
    
    return {
        "user_id": user_id,
        "username": username,
        "permissions": permissions
    }


# 策略：生成Telegram命令配置
@st.composite
def telegram_command_config_strategy(draw):
    """生成Telegram命令配置"""
    enabled = draw(st.booleans())
    
    # 生成授权用户列表
    authorized_users = draw(st.lists(
        authorized_user_config_strategy(),
        min_size=0,
        max_size=5
    ))
    
    return TelegramCommandConfig(
        enabled=enabled,
        authorized_users=authorized_users,
        execution_timeout_minutes=30,
        max_concurrent_executions=1,
        command_rate_limit={
            "max_commands_per_hour": 10,
            "cooldown_minutes": 5
        }
    )


# 模拟执行协调器
class MockExecutionCoordinator:
    """模拟执行协调器"""
    
    def __init__(self):
        self.execution_count = 0
    
    def is_execution_running(self):
        return False
    
    def run_once(self, trigger_type="manual", trigger_user=None):
        from crypto_news_analyzer.models import ExecutionResult
        self.execution_count += 1
        return ExecutionResult(
            execution_id=f"exec_{self.execution_count}",
            success=True,
            start_time=datetime.now(),
            end_time=datetime.now(),
            duration_seconds=1.0,
            items_processed=10,
            categories_found={"test": 5},
            errors=[],
            trigger_user=trigger_user,
            report_sent=True
        )
    
    def get_system_status(self):
        return {
            "initialized": True,
            "scheduler_running": False,
            "current_execution": None,
            "execution_history_count": self.execution_count,
            "next_execution_time": None
        }


@given(
    config=telegram_command_config_strategy(),
    test_user_id=user_id_strategy(),
    test_username=username_strategy()
)
@settings(max_examples=100, deadline=None)
def test_property_18_command_permission_verification_consistency(
    config: TelegramCommandConfig,
    test_user_id: str,
    test_username: str
):
    """
    **功能: crypto-news-analyzer, 属性 18: 命令权限验证一致性**
    **验证: 需求 16.5, 16.10, 16.11**
    
    属性: 对于任何通过Telegram发送的命令，系统应该验证发送者的权限，
    只有授权用户才能触发执行，未授权用户应该收到权限拒绝消息。
    
    验证策略:
    1. 创建命令处理器，配置授权用户列表
    2. 测试授权用户可以通过权限验证
    3. 测试未授权用户无法通过权限验证
    4. 测试用户对特定命令的权限验证
    5. 验证权限验证的一致性
    """
    # 创建模拟执行协调器
    mock_coordinator = MockExecutionCoordinator()
    
    # 创建命令处理器
    handler = TelegramCommandHandler(
        bot_token="test_token",
        execution_coordinator=mock_coordinator,
        config=config
    )
    
    # 属性1: 如果配置未启用，所有用户都应该被拒绝
    if not config.enabled:
        assert not handler.is_authorized_user(test_user_id, test_username), \
            "配置未启用时，所有用户都应该被拒绝"
        return  # 配置未启用时，后续测试无意义
    
    # 属性2: 检查测试用户是否在授权列表中
    is_authorized_by_id = any(
        str(user.get("user_id")) == test_user_id
        for user in config.authorized_users
    )
    is_authorized_by_username = any(
        user.get("username") == test_username
        for user in config.authorized_users
    )
    is_authorized = is_authorized_by_id or is_authorized_by_username
    
    # 属性3: is_authorized_user方法应该返回正确的授权状态
    actual_authorized = handler.is_authorized_user(test_user_id, test_username)
    assert actual_authorized == is_authorized, \
        f"权限验证不一致: 期望={is_authorized}, 实际={actual_authorized}"
    
    # 属性4: 如果用户被授权，验证命令权限
    if is_authorized:
        # 找到用户的权限配置（只检查通过ID授权的用户）
        user_config = None
        if is_authorized_by_id:
            for user in config.authorized_users:
                if str(user.get("user_id")) == test_user_id:
                    user_config = user
                    break
        
        if user_config:
            user_permissions = user_config.get("permissions", [])
            
            # 测试各种命令的权限
            for command in ["run", "status", "help"]:
                has_permission = handler.validate_user_permissions(test_user_id, command)
                
                # 如果权限列表为空，应该允许所有命令
                if not user_permissions:
                    assert has_permission, \
                        f"权限列表为空时，应该允许所有命令: {command}"
                else:
                    # 如果权限列表不为空，只允许列表中的命令
                    expected_permission = command in user_permissions
                    assert has_permission == expected_permission, \
                        f"命令权限验证不一致: 命令={command}, 期望={expected_permission}, 实际={has_permission}"
        elif is_authorized_by_username and not is_authorized_by_id:
            # 如果只通过用户名授权（没有匹配的user_id），validate_user_permissions应该返回False
            for command in ["run", "status", "help"]:
                has_permission = handler.validate_user_permissions(test_user_id, command)
                assert not has_permission, \
                    f"只通过用户名授权的用户，validate_user_permissions应该返回False: {command}"
    
    # 属性5: 未授权用户不应该有任何命令权限
    if not is_authorized:
        for command in ["run", "status", "help"]:
            has_permission = handler.validate_user_permissions(test_user_id, command)
            assert not has_permission, \
                f"未授权用户不应该有命令权限: {command}"
    
    # 属性6: 权限验证应该是幂等的（多次调用返回相同结果）
    result1 = handler.is_authorized_user(test_user_id, test_username)
    result2 = handler.is_authorized_user(test_user_id, test_username)
    assert result1 == result2, "权限验证应该是幂等的"
    
    # 属性7: 用户ID和用户名应该都能用于权限验证
    result_by_id = handler.is_authorized_user(test_user_id, None)
    result_by_username = handler.is_authorized_user(test_user_id, test_username)
    
    # 如果用户通过ID授权，两种方式都应该返回True
    if is_authorized_by_id:
        assert result_by_id, "通过ID授权的用户应该能通过ID验证"
        assert result_by_username, "通过ID授权的用户应该能通过ID+用户名验证"
    
    # 如果用户只通过用户名授权（不通过ID），则只有提供用户名时才能通过
    if is_authorized_by_username and not is_authorized_by_id:
        assert result_by_username, "通过用户名授权的用户应该能通过ID+用户名验证"


@given(
    config=telegram_command_config_strategy(),
    authorized_user_count=st.integers(min_value=1, max_value=5)
)
@settings(max_examples=50, deadline=None)
def test_property_18_authorized_users_consistency(
    config: TelegramCommandConfig,
    authorized_user_count: int
):
    """
    **功能: crypto-news-analyzer, 属性 18: 命令权限验证一致性 - 授权用户一致性**
    **验证: 需求 16.10**
    
    属性: 系统应该正确加载和管理授权用户列表，
    授权用户列表的大小应该与配置一致。
    """
    # 确保配置中有足够的授权用户
    assume(len(config.authorized_users) >= authorized_user_count)
    
    # 创建模拟执行协调器
    mock_coordinator = MockExecutionCoordinator()
    
    # 创建命令处理器
    handler = TelegramCommandHandler(
        bot_token="test_token",
        execution_coordinator=mock_coordinator,
        config=config
    )
    
    # 属性1: 授权用户缓存的大小应该与配置中唯一user_id的数量一致
    # （注意：可能有重复的user_id，所以缓存大小可能小于等于配置大小）
    unique_user_ids = set(str(user.get("user_id", "")) for user in config.authorized_users if user.get("user_id"))
    assert len(handler._authorized_users) == len(unique_user_ids), \
        f"授权用户缓存大小应该等于唯一user_id数量: cache={len(handler._authorized_users)}, unique={len(unique_user_ids)}"
    
    # 属性2: 配置中的每个授权用户都应该能通过权限验证
    for user_config in config.authorized_users:
        user_id = str(user_config.get("user_id", ""))
        username = user_config.get("username", "")
        
        if user_id and config.enabled:
            is_authorized = handler.is_authorized_user(user_id, username)
            assert is_authorized, \
                f"配置中的授权用户应该能通过验证: user_id={user_id}, username={username}"
    
    # 属性3: 对于有相同user_id的用户，缓存应该保存最后一个配置
    # （这是当前实现的行为，因为字典会覆盖相同的key）
    for user_id_str in handler._authorized_users:
        # 找到配置中所有具有该user_id的用户
        matching_users = [u for u in config.authorized_users if str(u.get("user_id")) == user_id_str]
        if matching_users:
            # 缓存中应该是最后一个匹配的用户配置
            cached_config = handler._authorized_users[user_id_str]
            last_matching_user = matching_users[-1]
            assert cached_config == last_matching_user, \
                f"对于重复的user_id，缓存应该保存最后一个配置: user_id={user_id_str}"


@given(
    user_id=user_id_strategy(),
    command_count=st.integers(min_value=1, max_value=15)
)
@settings(max_examples=50, deadline=None)
def test_property_18_rate_limit_consistency(
    user_id: str,
    command_count: int
):
    """
    **功能: crypto-news-analyzer, 属性 18: 命令权限验证一致性 - 速率限制一致性**
    **验证: 需求 16.5**
    
    属性: 系统应该正确实施速率限制，
    当用户超过限制时应该拒绝命令执行。
    """
    # 创建配置，设置较低的速率限制以便测试
    config = TelegramCommandConfig(
        enabled=True,
        authorized_users=[{
            "user_id": user_id,
            "username": "test_user",
            "permissions": ["run", "status", "help"]
        }],
        execution_timeout_minutes=30,
        max_concurrent_executions=1,
        command_rate_limit={
            "max_commands_per_hour": 10,
            "cooldown_minutes": 0  # 禁用冷却时间以便快速测试
        }
    )
    
    # 创建模拟执行协调器
    mock_coordinator = MockExecutionCoordinator()
    
    # 创建命令处理器
    handler = TelegramCommandHandler(
        bot_token="test_token",
        execution_coordinator=mock_coordinator,
        config=config
    )
    
    # 属性1: 在限制内的命令应该被允许
    allowed_count = 0
    rejected_count = 0
    
    for i in range(command_count):
        allowed, error_msg = handler.check_rate_limit(user_id)
        
        if allowed:
            allowed_count += 1
        else:
            rejected_count += 1
    
    # 属性2: 允许的命令数量不应该超过限制
    max_per_hour = config.command_rate_limit["max_commands_per_hour"]
    assert allowed_count <= max_per_hour, \
        f"允许的命令数量不应该超过限制: allowed={allowed_count}, limit={max_per_hour}"
    
    # 属性3: 如果命令数量超过限制，应该有被拒绝的命令
    if command_count > max_per_hour:
        assert rejected_count > 0, \
            f"命令数量超过限制时应该有被拒绝的命令: command_count={command_count}, rejected={rejected_count}"
        
        # 被拒绝的命令数量应该等于超出限制的数量
        expected_rejected = command_count - max_per_hour
        assert rejected_count == expected_rejected, \
            f"被拒绝的命令数量应该等于超出限制的数量: expected={expected_rejected}, actual={rejected_count}"
    
    # 属性4: 如果命令数量在限制内，所有命令都应该被允许
    if command_count <= max_per_hour:
        assert rejected_count == 0, \
            f"命令数量在限制内时不应该有被拒绝的命令: command_count={command_count}, rejected={rejected_count}"
        assert allowed_count == command_count, \
            f"命令数量在限制内时所有命令都应该被允许: expected={command_count}, actual={allowed_count}"


if __name__ == "__main__":
    # 运行属性测试
    pytest.main([__file__, "-v", "--tb=short"])
