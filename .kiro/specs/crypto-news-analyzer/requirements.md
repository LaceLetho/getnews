# 需求文档

## 介绍

加密货币新闻爬取和分析工具是一个自动化系统，用于从多个信息源收集加密货币相关新闻和社交媒体内容，并通过大模型进行智能分析和分类，生成结构化的新闻快讯报告。

## 术语表

- **System**: 加密货币新闻分析系统
- **RSS_Crawler**: RSS订阅源爬取组件
- **X_Crawler**: X/Twitter内容爬取组件  
- **Content_Analyzer**: 内容分析和分类组件
- **Report_Generator**: 报告生成组件
- **Time_Window**: 用户指定的时间窗口参数（小时数）
- **Auth_Token**: X/Twitter认证令牌
- **CT0**: X/Twitter认证参数
- **LLM_API_Key**: 大模型服务的API密钥
- **Telegram_Bot_Token**: Telegram机器人认证令牌
- **Telegram_Channel_ID**: Telegram频道标识符
- **Config_File**: 系统配置文件，存储信息源和认证参数
- **RSS_Source**: RSS订阅源配置项
- **X_Source**: X/Twitter信息源配置项
- **Scheduler**: 定时任务调度器
- **Execution_Interval**: 自动执行间隔时间
- **Content_Item**: 单条新闻或社交媒体内容
- **Category**: 六大信息分类类别之一
- **Retry_Budget**: 重试预算，用于管理API调用重试次数
- **Circuit_Breaker**: 断路器模式，用于防止连续失败的服务调用
- **Health_Check**: 健康检查机制，用于验证系统组件可用性
- **Property_Test**: 属性测试，验证系统在随机输入下的正确性
- **Integration_Test**: 集成测试，验证组件间协作和外部API集成
- **Exponential_Backoff**: 指数退避算法，用于智能重试延迟
- **Message_Splitting**: 消息分割机制，处理超长Telegram消息
- **Observability**: 可观测性，包括监控、日志和指标收集

## 需求

### 需求 1: 参数配置

**用户故事:** 作为用户，我希望能够配置分析参数，以便控制数据收集的范围和认证信息。

#### 验收标准

1. WHEN 用户启动系统 THEN System SHALL 接受时间窗口参数（小时数）
2. WHEN 用户提供X认证信息 THEN System SHALL 接受ct0和auth_token参数
3. WHEN 用户提供大模型认证信息 THEN System SHALL 接受LLM API密钥参数
4. WHEN 用户提供Telegram配置信息 THEN System SHALL 接受bot_token和channel_id参数
5. WHEN 参数无效或缺失 THEN System SHALL 返回明确的错误信息
6. THE System SHALL 验证时间窗口参数为正整数
7. THE System SHALL 验证认证参数格式的有效性
8. WHEN 接收到有效参数 THEN System SHALL 自动保存参数配置以供后续使用
9. WHEN 系统启动前 THEN System SHALL 检查所有必需参数的有效性
10. IF 发现参数无效或缺失 THEN System SHALL 及时提醒用户进行参数设置

### 需求 2: 配置文件管理

**用户故事:** 作为用户，我希望系统能够通过配置文件管理信息源和分析规则，以便方便地增减和修改数据源及分类标准。

#### 验收标准

1. THE System SHALL 创建和维护一个配置文件存储所有信息源和分析规则
2. THE Config_File SHALL 包含所有RSS订阅源的URL和描述信息
3. THE Config_File SHALL 包含所有X/Twitter信息源的URL和描述信息
4. THE Config_File SHALL 存储认证参数（ct0、auth_token、LLM API密钥、Telegram配置）
5. THE Config_File SHALL 包含内容分类类别定义和对应的识别规则
6. THE Config_File SHALL 包含需要忽略的内容类型定义
7. WHEN 系统启动前 THEN System SHALL 读取并验证配置文件的有效性
8. WHEN 配置文件不存在 THEN System SHALL 创建默认配置文件包含预设信息源和默认分类标准
9. WHEN 配置文件格式无效 THEN System SHALL 提供详细的格式错误位置和修复建议
10. THE System SHALL 支持用户通过编辑配置文件来增加、删除或修改信息源和分类规则
11. WHEN 配置文件更新 THEN System SHALL 在下次运行时使用新的配置
12. THE System SHALL 验证配置文件中每个信息源URL的格式有效性
13. THE System SHALL 验证配置文件中分类规则的格式有效性
14. THE System SHALL 验证配置文件结构的完整性，确保所有必需字段都存在
15. WHEN 配置文件包含无效的JSON语法 THEN System SHALL 指出具体的语法错误位置
16. THE System SHALL 支持配置文件的向后兼容性，能够处理旧版本的配置格式
17. WHEN 配置参数类型不匹配 THEN System SHALL 提供类型转换建议或默认值

### 需求 3: RSS内容爬取

**用户故事:** 作为用户，我希望系统能够从配置文件读取RSS订阅源并自动爬取内容，以便获取全面的新闻信息。

#### 验收标准

1. THE System SHALL 从配置文件读取所有RSS订阅源URL
2. THE System SHALL 爬取配置文件中定义的每个RSS订阅源
3. WHEN RSS源不可访问 THEN System SHALL 记录错误状态并继续处理其他源
4. WHEN 爬取RSS内容 THEN System SHALL 提取标题、内容、发布时间和原文链接
5. WHEN 内容发布时间超出时间窗口 THEN System SHALL 过滤掉该内容
6. THE System SHALL 支持标准RSS 2.0和Atom格式的订阅源
7. WHEN 配置文件中RSS源为空 THEN System SHALL 跳过RSS爬取阶段
8. THE RSS_Crawler SHALL 使用正确的构造函数参数（time_window_hours）进行初始化
9. WHEN RSS源返回无效的XML格式 THEN System SHALL 记录解析错误并跳过该源
10. THE System SHALL 处理RSS源的重定向和HTTP状态码错误
11. WHEN RSS源需要特殊编码处理 THEN System SHALL 自动检测并正确解码内容
12. THE System SHALL 设置合理的HTTP超时时间，避免长时间等待无响应的源

### 需求 4: X/Twitter内容爬取

**用户故事:** 作为用户，我希望系统能够从配置文件读取X/Twitter信息源并爬取内容，以便获取社交媒体上的实时信息。

#### 验收标准

1. THE System SHALL 从配置文件读取所有X/Twitter信息源URL
2. THE System SHALL 爬取配置文件中定义的每个X列表和时间线
3. WHEN 使用X认证参数 THEN System SHALL 通过ct0和auth_token进行身份验证
4. WHEN X API调用失败 THEN System SHALL 记录错误状态并继续处理其他源
5. WHEN 爬取X内容 THEN System SHALL 提取推文文本、发布时间和原文链接
6. WHEN 推文发布时间超出时间窗口 THEN System SHALL 过滤掉该推文
7. WHEN 配置文件中X信息源为空 THEN System SHALL 跳过X爬取阶段

### 需求 5: 内容智能分析和分类

**用户故事:** 作为用户，我希望系统能够智能分析收集到的内容并按照可配置的类别进行分类，以便快速了解不同类型的市场信息。

#### 验收标准

1. WHEN 分析内容 THEN System SHALL 使用大模型进行内容理解和分类
2. WHEN 大模型API调用 THEN System SHALL 使用提供的LLM API密钥进行认证
3. THE Content_Analyzer SHALL 根据配置文件中定义的分类标准进行内容分类
4. THE Config_File SHALL 包含可配置的内容分类类别和对应的识别规则
5. THE System SHALL 支持默认的六大类别配置：大户动向、利率事件、美国政府监管政策、安全事件、新产品、市场新现象
6. THE Content_Analyzer SHALL 支持用户自定义新的分类类别和识别规则
7. THE Config_File SHALL 定义需要忽略的内容类型（如广告软文、重复信息、情绪发泄、空洞预测和立场争论）
8. WHEN 内容属于忽略类别 THEN System SHALL 过滤掉该内容
9. WHEN 内容无法分类 THEN System SHALL 标记为未分类但保留在报告中
10. WHEN 配置文件中分类规则更新 THEN System SHALL 在下次运行时使用新的分类规则
11. THE System SHALL 支持MiniMax LLM API作为主要分析引擎，确保100%成功率
12. WHEN LLM API调用失败 THEN System SHALL 实施重试机制，最多重试3次
13. THE Content_Analyzer SHALL 返回结构化的分析结果，包含分类、置信度、推理和关键点
14. WHEN 批量分析内容 THEN System SHALL 保持每个内容项分析结果的一致性和完整性
15. THE System SHALL 验证分析结果的格式正确性，确保所有必需字段都存在
16. WHEN 分析结果置信度低于阈值 THEN System SHALL 标记为低置信度并记录原因

### 需求 6: 爬取状态监控

**用户故事:** 作为用户，我希望了解各个数据源的爬取状态，以便知道数据收集的完整性。

#### 验收标准

1. THE System SHALL 记录每个RSS订阅源的爬取状态（成功/失败）
2. THE System SHALL 记录每个RSS订阅源的获取数量
3. THE System SHALL 记录每个X列表的爬取状态（成功/失败）
4. THE System SHALL 记录每个X列表的获取数量
5. WHEN 数据源爬取失败 THEN System SHALL 记录具体的错误原因
6. THE System SHALL 在最终报告中展示所有数据源的状态信息

### 需求 7: 结构化报告生成

**用户故事:** 作为用户，我希望获得格式化的分析报告，以便快速浏览和理解收集到的信息。

#### 验收标准

1. THE Report_Generator SHALL 生成包含时间窗口信息的报告头部
2. THE Report_Generator SHALL 生成网站爬取状态表格，显示每个数据源的状态和获取数量
3. THE Report_Generator SHALL 按配置文件中定义的分类标准组织分析结果
4. THE System SHALL 支持通过配置文件灵活调整分析规则和分类标准
5. THE Config_File SHALL 包含可配置的内容分类类别定义
6. WHEN 生成分类内容 THEN System SHALL 为每条信息包含原文链接
7. THE Report_Generator SHALL 生成可选的总结部分，突出最重要的信息
8. THE Report_Generator SHALL 使用Markdown格式输出报告
9. WHEN 某个类别没有内容 THEN System SHALL 在报告中显示该类别为空
10. WHEN 配置文件中分类标准更新 THEN System SHALL 在下次运行时使用新的分类标准

### 需求 8: Telegram报告发送

**用户故事:** 作为用户，我希望系统能够自动将生成的报告发送到指定的Telegram频道，以便及时获得分析结果。

#### 验收标准

1. WHEN 报告生成完成 THEN System SHALL 通过Telegram Bot发送报告到指定频道
2. WHEN 发送Telegram消息 THEN System SHALL 使用保存的bot_token进行认证
3. WHEN 发送Telegram消息 THEN System SHALL 发送到指定的channel_id
4. THE System SHALL 保持报告的Markdown格式在Telegram中的可读性
5. WHEN Telegram发送失败 THEN System SHALL 记录错误信息并提供本地报告备份
6. THE System SHALL 验证Telegram Bot Token的有效性
7. THE System SHALL 验证Telegram Channel ID的可访问性
8. WHEN 报告超过Telegram消息长度限制 THEN System SHALL 智能分割消息并保持内容完整性
9. WHEN 消息发送失败 THEN System SHALL 实施指数退避重试机制，最多重试3次
10. THE System SHALL 为每个消息部分独立管理重试预算，避免重试次数累积错误
11. WHEN 网络连接不稳定 THEN System SHALL 优雅处理连接错误并继续尝试发送剩余部分
12. THE System SHALL 支持多种Channel ID格式（@username、负数ID、正数ID）
13. WHEN 部分消息发送成功 THEN System SHALL 记录成功发送的部分数量和总部分数量
14. THE System SHALL 在发送失败时自动创建带时间戳的本地备份文件

### 需求 9: Docker化部署和容器调度

**用户故事:** 作为用户，我希望系统能够通过Docker容器化部署，支持一次性执行模式和cron定时调度，以便在服务器环境中高效运行和管理。

#### 验收标准

1. THE System SHALL 提供主控制器支持一次性执行模式，执行完整工作流后自动退出
2. THE System SHALL 提供Dockerfile将项目完整打包成Docker容器
3. THE System SHALL 提供docker-compose.yml文件支持容器启动和管理
4. THE System SHALL 支持通过`docker-compose run --rm my-service`命令执行完成后自动退出
5. THE System SHALL 提供shell脚本支持crontab定时运行服务
6. THE System SHALL 支持cron表达式如`0 */6 * * * /usr/local/bin/docker-compose -f /path/to/your/docker-compose.yml up -d`进行定时调度
7. THE System SHALL 支持通过环境变量进行配置管理，覆盖配置文件设置
8. THE System SHALL 实现容器健康检查机制，验证服务可用性
9. THE System SHALL 支持数据卷挂载，包括配置文件、日志目录和数据存储
10. WHEN 容器接收到停止信号 THEN System SHALL 优雅停止并清理资源
11. THE System SHALL 在容器启动时验证所有必需的环境变量和挂载卷
12. WHEN 容器环境配置无效 THEN System SHALL 快速失败并提供明确的错误信息
13. THE System SHALL 提供轻量级的基础镜像，优化容器启动时间和资源占用
14. THE System SHALL 支持容器日志的标准输出，便于日志收集和监控
15. THE System SHALL 根据执行结果返回适当的退出状态码（0=成功，非0=失败）

### 需求 10: 时间窗口过滤

**用户故事:** 作为用户，我希望只分析指定时间窗口内的内容，以便获得时效性强的信息。

#### 验收标准

1. WHEN 处理任何内容 THEN System SHALL 检查其发布时间是否在指定的时间窗口内
2. THE System SHALL 计算时间窗口为当前时间向前推算指定小时数
3. WHEN 内容发布时间早于时间窗口起始时间 THEN System SHALL 排除该内容
4. THE System SHALL 在报告中显示实际的数据时间窗口范围
5. WHEN 时间窗口参数为0或负数 THEN System SHALL 返回错误信息

### 需求 11: 错误处理和容错

**用户故事:** 作为系统管理员，我希望系统能够优雅地处理各种错误情况，以便保证系统的稳定性和可用性。

#### 验收标准

1. WHEN 网络连接失败 THEN System SHALL 记录错误并继续处理其他数据源
2. WHEN RSS解析失败 THEN System SHALL 记录错误详情并跳过该订阅源
3. WHEN X API认证失败 THEN System SHALL 返回明确的认证错误信息
4. WHEN 大模型API认证失败 THEN System SHALL 返回明确的API密钥错误信息
5. WHEN Telegram Bot认证失败 THEN System SHALL 返回明确的Bot Token错误信息
6. WHEN 大模型API调用失败 THEN System SHALL 记录错误并将内容标记为未分析
7. IF 所有数据源都失败 THEN System SHALL 生成包含错误信息的报告
8. THE System SHALL 为每种错误类型提供具体的错误描述
9. WHEN 部分数据源成功 THEN System SHALL 基于可用数据生成报告并标注数据源状态
10. WHEN API调用超时 THEN System SHALL 实施超时重试机制，避免无限等待
11. WHEN 配置文件格式错误 THEN System SHALL 提供详细的格式错误位置和修复建议
12. WHEN 系统资源不足 THEN System SHALL 优雅降级，优先保证核心功能运行
13. THE System SHALL 实施断路器模式，在连续失败时暂时停止调用失败的服务
14. WHEN 临时文件创建失败 THEN System SHALL 尝试使用备用目录或内存缓存
15. THE System SHALL 记录所有错误的详细上下文信息，包括时间戳、错误类型和堆栈跟踪

### 需求 12: 系统健壮性和生产就绪

**用户故事:** 作为系统管理员，我希望系统具备生产环境所需的健壮性和可靠性，以便在真实环境中稳定运行。

#### 验收标准

1. THE System SHALL 通过真实API环境的集成测试验证
2. WHEN 系统部署到生产环境 THEN System SHALL 保持与测试环境相同的功能表现
3. THE System SHALL 实施全面的属性测试覆盖，验证系统在各种输入下的正确性
4. WHEN 发现系统bug THEN System SHALL 有完整的回归测试防止相同问题再次出现
5. THE System SHALL 支持真实API token的配置和验证
6. WHEN API服务不可用 THEN System SHALL 优雅降级并提供有意义的错误信息
7. THE System SHALL 记录详细的操作日志，包括成功和失败的API调用
8. WHEN 系统运行异常 THEN System SHALL 提供足够的诊断信息用于问题排查
9. THE System SHALL 实施健康检查机制，定期验证关键组件的可用性
10. WHEN 系统资源使用异常 THEN System SHALL 发出告警并采取保护措施

### 需求 13: 重试机制和可靠性

**用户故事:** 作为用户，我希望系统在面临临时故障时能够智能重试，以便提高操作成功率和系统可靠性。

#### 验收标准

1. THE System SHALL 为所有外部API调用实施统一的重试机制
2. WHEN API调用失败 THEN System SHALL 使用指数退避算法进行重试
3. THE System SHALL 为不同类型的错误设置不同的重试策略
4. WHEN 重试次数达到上限 THEN System SHALL 记录最终失败状态并继续处理其他任务
5. THE System SHALL 正确管理重试预算，避免重试次数累积错误
6. WHEN 消息需要分割发送 THEN System SHALL 为每个部分独立管理重试预算
7. THE System SHALL 区分可重试错误（网络超时、限流）和不可重试错误（认证失败、格式错误）
8. WHEN 遇到限流错误 THEN System SHALL 遵守API提供商的重试延迟建议
9. THE System SHALL 记录重试统计信息，用于监控和优化重试策略
10. WHEN 连续重试失败 THEN System SHALL 实施断路器模式，暂时停止调用失败的服务

### 需求 14: 测试和质量保证

**用户故事:** 作为开发者，我希望系统有完善的测试覆盖，以便确保代码质量和功能正确性。

#### 验收标准

1. THE System SHALL 实施单元测试覆盖所有核心功能模块
2. THE System SHALL 实施集成测试验证组件间的协作
3. THE System SHALL 实施属性测试验证系统在随机输入下的正确性
4. THE System SHALL 实施真实环境测试验证与外部API的集成
5. WHEN 发现bug THEN System SHALL 添加对应的回归测试防止问题重现
6. THE System SHALL 验证所有配置参数的有效性和边界条件
7. THE System SHALL 测试错误处理路径，确保异常情况下的系统稳定性
8. THE System SHALL 验证消息分割和重试机制的正确性
9. THE System SHALL 测试配置文件的各种格式和内容组合
10. THE System SHALL 验证LLM分析结果的一致性和完整性
11. THE System SHALL 实施性能测试，确保批量处理的效率
12. WHEN 测试失败 THEN System SHALL 提供详细的失败原因和调试信息

### 需求 15: 监控和可观测性

**用户故事:** 作为运维人员，我希望能够监控系统的运行状态和性能指标，以便及时发现和解决问题。

#### 验收标准

1. THE System SHALL 记录所有关键操作的执行时间和结果状态
2. THE System SHALL 提供API调用成功率和响应时间的统计信息
3. THE System SHALL 监控系统资源使用情况（内存、CPU、磁盘）
4. WHEN 关键指标异常 THEN System SHALL 生成告警通知
5. THE System SHALL 记录详细的错误日志，包括错误类型、时间戳和上下文信息
6. THE System SHALL 提供系统健康状态的实时查询接口
7. THE System SHALL 统计各个数据源的爬取成功率和获取数量
8. THE System SHALL 监控LLM分析的处理时间和分类分布
9. THE System SHALL 记录Telegram发送的成功率和消息分割统计
10. THE System SHALL 提供可视化的监控面板显示关键指标趋势