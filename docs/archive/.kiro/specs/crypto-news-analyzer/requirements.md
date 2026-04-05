# 需求文档

## 介绍

加密货币新闻爬取和分析工具是一个自动化系统，用于从多个信息源收集加密货币相关新闻和社交媒体内容，并通过大模型进行智能分析和分类，生成结构化的新闻快讯报告。

## 术语表

- **System**: 加密货币新闻分析系统
- **RSS_Crawler**: RSS订阅源爬取组件
- **X_Crawler**: X/Twitter内容爬取组件，通过bird工具实现
- **Bird_Tool**: 第三方X/Twitter数据获取工具 (https://github.com/steipete/bird)
- **Bird_Wrapper**: Python封装层，用于调用bird工具的命令行接口  
- **Content_Analyzer**: 内容分析和分类组件
- **Report_Generator**: 报告生成组件
- **Market_Snapshot_Service**: 联网AI服务，用于获取当前市场现状快照
- **Grok_API**: X平台的联网AI服务，用于获取实时市场信息
- **Structured_Output_Tool**: 结构化输出工具（如instructor库），强制大模型返回结构化数据
- **Dynamic_Classification**: 动态分类系统，根据大模型返回结果自动调整分类展示
- **Time_Window**: 用户指定的时间窗口参数（小时数）
- **Auth_Token**: X/Twitter认证令牌
- **CT0**: X/Twitter认证参数
- **LLM_API_Key**: 大模型服务的API密钥
- **Grok_API_Key**: Grok联网AI服务的API密钥
- **Telegram_Bot_Token**: Telegram机器人认证令牌
- **Telegram_Channel_ID**: Telegram频道标识符
- **Config_File**: 系统配置文件，存储信息源和认证参数
- **RSS_Source**: RSS订阅源配置项
- **X_Source**: X/Twitter信息源配置项
- **Market_Summary_Prompt**: 市场快照获取提示词模板
- **Analysis_Prompt**: 内容分析提示词模板
- **Scheduler**: 定时任务调度器
- **Execution_Interval**: 自动执行间隔时间
- **Content_Item**: 单条新闻或社交媒体内容
- **Category**: 动态分类类别，由大模型返回决定
- **Weight_Score**: 消息重要性评分（0-100）
- **Retry_Budget**: 重试预算，用于管理API调用重试次数
- **Circuit_Breaker**: 断路器模式，用于防止连续失败的服务调用
- **Health_Check**: 健康检查机制，用于验证系统组件可用性
- **Property_Test**: 属性测试，验证系统在随机输入下的正确性
- **Integration_Test**: 集成测试，验证组件间协作和外部API集成
- **Exponential_Backoff**: 指数退避算法，用于智能重试延迟
- **Message_Splitting**: 消息分割机制，处理超长Telegram消息
- **Telegram_Formatting**: Telegram格式化，适配Telegram消息显示特点
- **Hyperlink_Formatting**: 超链接格式化，将source字段转换为Telegram可点击链接
- **Observability**: 可观测性，包括监控、日志和指标收集
- **Telegram_Command**: Telegram命令，用户通过发送特定消息触发系统执行
- **Command_Handler**: 命令处理器，解析和执行Telegram命令
- **Manual_Trigger**: 手动触发，通过外部命令启动系统执行
- **Bot**: Telegram bot应用程序，接收和处理命令
- **Private_Chat**: 用户与Bot之间的一对一对话
- **Group_Chat**: 多个用户和Bot参与的Telegram群组对话
- **Authorized_User**: 其user_id或username在授权用户配置中列出的用户
- **User_ID**: Telegram分配给每个用户的唯一数字标识符
- **Username**: 以"@"开头的Telegram用户名（handle），唯一标识用户
- **Chat_ID**: 聊天的唯一标识符（私聊为正数，群组为负数）
- **Command_Sender**: 向Bot发送命令的用户
- **Username_Resolution**: 使用Telegram Bot API将用户名转换为对应user_id的过程
- **Username_Cache**: 用户名到user_id的内存映射，避免重复API调用
- **Chat_Context**: 从Telegram更新中提取的聊天上下文信息

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

**用户故事:** 作为用户，我希望系统能够从配置文件读取X/Twitter信息源并通过bird工具爬取内容，以便获取社交媒体上的实时信息并避免复杂的反爬机制。

#### 验收标准

1. THE System SHALL 从配置文件读取所有X/Twitter信息源URL
2. THE System SHALL 通过bird工具爬取配置文件中定义的每个X列表和时间线
3. THE System SHALL 安装并配置bird工具作为X/Twitter数据获取的底层工具
4. THE System SHALL 创建Python封装层调用bird工具的命令行接口
5. WHEN 调用bird工具 THEN System SHALL 通过命令行参数传递认证信息和目标URL
6. WHEN bird工具执行失败 THEN System SHALL 记录错误状态并继续处理其他源
7. WHEN 爬取X内容 THEN System SHALL 解析bird工具的输出并提取推文文本、发布时间和原文链接
8. WHEN 推文发布时间超出时间窗口 THEN System SHALL 过滤掉该推文
9. WHEN 配置文件中X信息源为空 THEN System SHALL 跳过X爬取阶段
10. THE System SHALL 处理bird工具的各种输出格式和错误状态
11. WHEN bird工具不可用或未正确安装 THEN System SHALL 返回明确的依赖错误信息
12. THE System SHALL 通过bird工具的配置文件或环境变量管理X/Twitter认证信息
13. WHEN 爬取X内容前 THEN System SHALL 查询本地数据库中该信息源最近一条消息的发布时间
14. THE System SHALL 计算当前时间与最近消息时间的时间差（使用UTC时区）
15. THE System SHALL 根据公式"min(时间差/6小时向上取整, max_pages_limit)"计算bird工具的--max-pages参数
16. WHEN 本地数据库中没有该信息源的历史数据 THEN System SHALL 使用配置文件中的max_pages_limit作为默认值
17. THE System SHALL 确保计算出的max_pages不超过配置文件中的max_pages_limit值
18. THE System SHALL 使用计算出的max_pages参数调用bird工具，以避免X平台风控
19. THE System SHALL 确保所有时间计算使用UTC时区，避免时区差异导致的错误

### 需求 5: 内容智能分析和分类

**用户故事:** 作为用户，我希望系统能够通过多步骤的智能分析流程对收集到的内容进行分类和过滤，以便获得准确的市场信息和动态分类结果。

#### 验收标准

1. WHEN 开始内容分析 THEN System SHALL 首先使用联网AI获取当前市场现状快照
2. THE System SHALL 使用prompts/market_summary_prompt.md中的提示词向联网AI请求市场快照
3. THE System SHALL 支持Grok作为联网AI服务获取实时市场信息
4. WHEN 获取市场快照 THEN System SHALL 合并市场快照和analysis_prompt.md提示词作为系统提示词
5. THE System SHALL 使用结构化输出工具（如instructor库）强制大模型返回结构化数据
6. WHEN 分析内容 THEN System SHALL 将所有新闻批量作为用户提示词发送给大模型
7. THE System SHALL 通过提示词让大模型完成语义去重和筛选过滤工作
8. THE System SHALL 支持动态分类，不在代码中硬编码具体类别
9. WHEN 大模型返回分类结果 THEN System SHALL 根据返回数据中的类别数量动态展示分类
10. THE System SHALL 支持分类标准的灵活变动，通过修改提示词实现分类调整
11. THE System SHALL 支持多种大模型服务（Grok、MiniMax M2.1等）作为分析引擎
12. WHEN 大模型API调用失败 THEN System SHALL 实施重试机制，最多重试3次
13. THE Content_Analyzer SHALL 返回结构化的分析结果，包含time、category、weight_score、summary和source字段
14. WHEN 批量分析内容 THEN System SHALL 保持每个内容项分析结果的一致性和完整性
15. THE System SHALL 验证分析结果的JSON格式正确性，确保所有必需字段都存在
16. WHEN 某批次数据全被过滤 THEN System SHALL 接受空列表[]作为有效返回结果
17. THE System SHALL 支持通过提示词配置需要忽略的内容类型和过滤规则
18. WHEN 联网AI服务不可用 THEN System SHALL 记录错误并使用默认市场快照继续分析

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

**用户故事:** 作为用户，我希望获得适配Telegram格式的结构化分析报告，以便在Telegram上快速浏览和理解收集到的信息。

#### 验收标准

1. THE Report_Generator SHALL 生成适配Telegram格式的报告，而非纯Markdown格式
2. THE Report_Generator SHALL 在报告头部包含数据时间窗口和数据时间范围信息
3. THE Report_Generator SHALL 生成数据源爬取状态部分，显示每个数据源的状态和获取数量
4. THE Report_Generator SHALL 按大模型返回的分类动态组织各消息大类
5. THE System SHALL 支持动态分类展示，根据大模型返回的类别数量自动调整报告结构
6. WHEN 展示具体消息 THEN System SHALL 包含大模型返回的所有字段（time、category、weight_score、summary、source）
7. THE Report_Generator SHALL 将source字段格式化为Telegram超链接形式
8. THE Report_Generator SHALL 优化Telegram消息格式，确保在移动端的可读性
9. WHEN 某个类别没有内容 THEN System SHALL 在报告中显示该类别为空或完全省略该类别
10. THE Report_Generator SHALL 支持Telegram的文本格式化语法（粗体、斜体、代码块等）
11. WHEN 报告内容过长 THEN System SHALL 智能分割消息并保持内容完整性
12. THE Report_Generator SHALL 为每个消息类别使用适当的Telegram格式化标记
13. THE Report_Generator SHALL 确保超链接在Telegram中正确显示和可点击
14. THE Report_Generator SHALL 支持Telegram的特殊字符转义，避免格式错误
15. THE Report_Generator SHALL 优化报告布局，适应Telegram的消息显示特点

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

### 需求 9: Docker化部署和内部定时调度

**用户故事:** 作为用户，我希望系统能够通过Docker容器化部署，支持一次性执行模式和内部定时调度，以便在Railway等云平台环境中高效运行和管理。

#### 验收标准

1. THE System SHALL 提供主控制器支持一次性执行模式，执行完整工作流后自动退出
2. THE System SHALL 提供内部定时调度器，支持程序内部的周期性任务执行
3. THE System SHALL 支持通过配置文件或环境变量设置调度间隔（如每6小时执行一次）
4. THE System SHALL 提供Dockerfile将项目完整打包成Docker容器
5. THE System SHALL 支持通过Docker命令执行一次性任务和持续运行的定时调度模式
6. THE Scheduler SHALL 在指定的时间间隔自动触发完整的数据收集和分析工作流
7. WHEN 运行在定时调度模式 THEN System SHALL 持续运行直到接收到停止信号
8. THE System SHALL 支持通过环境变量进行配置管理，覆盖配置文件设置
9. THE System SHALL 实现容器健康检查机制，验证服务可用性
10. THE System SHALL 支持数据卷挂载，包括配置文件、日志目录和数据存储
11. WHEN 容器接收到停止信号 THEN System SHALL 优雅停止并清理资源
12. THE System SHALL 在容器启动时验证所有必需的环境变量和挂载卷
13. WHEN 容器环境配置无效 THEN System SHALL 快速失败并提供明确的错误信息
14. THE System SHALL 提供轻量级的基础镜像，优化容器启动时间和资源占用
15. THE System SHALL 支持容器日志的标准输出，便于日志收集和监控
16. THE System SHALL 根据执行结果返回适当的退出状态码（0=成功，非0=失败）
17. THE Scheduler SHALL 记录每次执行的开始时间、结束时间和执行状态
18. WHEN 定时任务执行失败 THEN System SHALL 记录错误信息并在下个调度周期继续尝试

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
3. WHEN bird工具执行失败 THEN System SHALL 记录详细的工具错误信息并跳过该X源
4. WHEN bird工具未安装或配置错误 THEN System SHALL 返回明确的依赖错误信息
5. WHEN bird工具输出格式异常 THEN System SHALL 记录解析错误并跳过该批次数据
6. WHEN 大模型API认证失败 THEN System SHALL 返回明确的API密钥错误信息
7. WHEN Telegram Bot认证失败 THEN System SHALL 返回明确的Bot Token错误信息
8. WHEN 大模型API调用失败 THEN System SHALL 记录错误并将内容标记为未分析
9. IF 所有数据源都失败 THEN System SHALL 生成包含错误信息的报告
10. THE System SHALL 为每种错误类型提供具体的错误描述
11. WHEN 部分数据源成功 THEN System SHALL 基于可用数据生成报告并标注数据源状态
12. WHEN API调用超时 THEN System SHALL 实施超时重试机制，避免无限等待
13. WHEN 配置文件格式错误 THEN System SHALL 提供详细的格式错误位置和修复建议
14. WHEN 系统资源不足 THEN System SHALL 优雅降级，优先保证核心功能运行
15. THE System SHALL 实施断路器模式，在连续失败时暂时停止调用失败的服务
16. WHEN 临时文件创建失败 THEN System SHALL 尝试使用备用目录或内存缓存
17. THE System SHALL 记录所有错误的详细上下文信息，包括时间戳、错误类型和堆栈跟踪
18. WHEN bird工具返回认证错误 THEN System SHALL 提供bird工具配置指导信息
19. WHEN bird工具进程超时 THEN System SHALL 终止进程并记录超时错误

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

### 需求 16: Telegram命令触发和多用户授权

**用户故事:** 作为用户，我希望能够通过向Telegram Bot发送命令来手动触发一次程序运行或查询市场快照，并且系统支持多个授权用户在私聊和群组中与bot交互，以便在需要时立即获取最新的分析报告或市场信息。

#### 验收标准

1. THE System SHALL 支持通过Telegram Bot接收用户命令
2. WHEN 用户发送"/run"命令 THEN System SHALL 立即触发一次完整的数据收集和分析工作流
3. WHEN 用户发送"/market"命令 THEN System SHALL 获取并返回当前市场现状快照
4. WHEN 用户发送"/status"命令 THEN System SHALL 返回当前系统运行状态和上次执行信息
5. WHEN 用户发送"/help"命令 THEN System SHALL 返回可用命令列表和使用说明
6. WHEN 用户发送"/tokens"命令 THEN System SHALL 返回当前会话的token使用统计
7. THE System SHALL 验证命令发送者的权限，只允许授权用户触发执行
8. WHEN 系统正在执行任务 THEN System SHALL 拒绝新的执行命令并返回当前执行状态
9. WHEN 手动触发执行完成 THEN System SHALL 发送执行结果通知给触发用户
10. THE System SHALL 记录所有手动触发的执行历史和触发用户信息
11. WHEN 手动触发执行失败 THEN System SHALL 发送详细的错误信息给触发用户
12. THE System SHALL 从TELEGRAM_AUTHORIZED_USERS环境变量读取授权用户列表
13. THE TELEGRAM_AUTHORIZED_USERS环境变量 SHALL 包含逗号分隔的Telegram用户ID和/或用户名列表
14. WHEN Bot初始化时 THEN System SHALL 解析TELEGRAM_AUTHORIZED_USERS变量并加载所有条目到内存
15. WHEN TELEGRAM_AUTHORIZED_USERS变量为空或未设置 THEN System SHALL 记录警告并拒绝所有命令尝试
16. THE System SHALL 支持多个用户在授权列表中，数量不受限制
17. THE System SHALL 在解析时修剪每个条目的空格以处理格式变化
18. WHEN 环境变量中的条目是数字 THEN System SHALL 将其视为用户ID
19. WHEN 环境变量中的条目以"@"开头 THEN System SHALL 将其视为用户名
20. WHEN 环境变量中的条目既不是数字也不以"@"开头 THEN System SHALL 记录警告并跳过该条目
21. WHEN TELEGRAM_AUTHORIZED_USERS中提供用户名（以"@"开头） THEN System SHALL 使用Telegram Bot API将其解析为对应的user_id
22. WHEN Bot收到用户命令 THEN System SHALL 检查发送者的user_id是否匹配任何从用户名条目解析的user_id
23. WHEN 用户名解析成功 THEN System SHALL 缓存用户名到user_id的映射以避免重复API调用
24. WHEN 用户名解析因用户未找到而失败 THEN System SHALL 记录警告并跳过该用户名条目
25. WHEN 用户名解析因API错误而失败 THEN System SHALL 记录错误并跳过该用户名条目
26. THE System SHALL 在接受命令前在初始化期间尝试用户名解析
27. THE System SHALL 在同一TELEGRAM_AUTHORIZED_USERS变量中支持数字用户ID和@username条目的混合格式
28. WHEN 授权用户在私聊中发送命令 THEN System SHALL 验证命令发送者的User_ID并处理命令
29. WHEN 授权用户在群组中发送命令 THEN System SHALL 验证命令发送者的User_ID（而非群组ID）并处理命令
30. WHEN 未授权用户发送命令 THEN System SHALL 返回权限拒绝消息
31. THE System SHALL 支持在定时调度模式和命令触发模式之间切换
32. WHEN 收到无效命令 THEN System SHALL 返回友好的错误提示和帮助信息
33. THE System SHALL 为手动触发的执行设置超时限制，避免长时间占用资源
34. WHEN 手动触发执行超时 THEN System SHALL 终止执行并通知用户
35. WHEN 用户发送"/market"命令 THEN System SHALL 使用联网AI服务获取实时市场快照
36. WHEN 市场快照获取成功 THEN System SHALL 将市场快照以Telegram格式发送给用户
37. WHEN 市场快照获取失败 THEN System SHALL 返回错误信息并说明失败原因
38. THE System SHALL 记录所有授权尝试，包括user_id、username、聊天类型和授权决定
39. WHEN 授权失败 THEN System SHALL 记录失败原因
40. WHEN 授权成功 THEN System SHALL 记录正在执行的命令和触发用户
41. THE System SHALL 在所有授权日志中包含聊天上下文信息（私聊vs群组）
42. THE System SHALL 为所有授权用户提供相同的权限集（/run, /status, /help, /market, /tokens）
43. WHEN 手动触发的/run命令执行时 THEN System SHALL 将报告发送到触发命令的聊天窗口（私聊或群组）
44. WHEN 定时任务报告生成时 THEN System SHALL 将报告发送到TELEGRAM_CHANNEL_ID指定的频道

### 需求 17: 已发送消息缓存和去重

**用户故事:** 作为用户，我希望系统能够记住已经发送过的新闻消息，避免在下次scheduled任务执行时重复发送相同的内容，以便获得更高质量的信息流。

#### 验收标准

1. WHEN 报告发送成功 THEN System SHALL 将已发送的新闻消息缓存到本地存储
2. THE System SHALL 为每条缓存的消息记录发送时间戳
3. THE System SHALL 设置缓存有效期为24小时
4. WHEN 缓存消息超过24小时 THEN System SHALL 自动清理过期的缓存记录
5. WHEN 下次scheduled任务执行时 THEN System SHALL 从缓存中读取24小时内已发送的消息
6. THE System SHALL 将缓存的消息格式化为简洁的文本摘要
7. THE System SHALL 将缓存的消息摘要合并到analysis_prompt.md的${outdated_news}占位符中
8. WHEN 大模型分析新内容时 THEN System SHALL 使用包含outdated_news的完整提示词
9. THE System SHALL 确保大模型能够识别并过滤掉与缓存消息重复的内容
10. WHEN 缓存为空时 THEN System SHALL 在${outdated_news}位置填充"无"或空字符串
11. THE System SHALL 支持配置缓存有效期（默认24小时）
12. THE System SHALL 在系统启动时自动清理过期的缓存记录
13. WHEN 手动触发的/run命令执行时 THEN System SHALL 同样使用缓存机制避免重复
14. THE System SHALL 记录缓存命中统计信息，用于监控去重效果
15. WHEN 缓存存储失败 THEN System SHALL 记录错误但不影响报告发送流程