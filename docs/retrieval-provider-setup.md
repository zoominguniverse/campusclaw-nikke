# 真实服务配置

问答与embedding可以使用不同服务商。以下为建议配置，不表示已经开通或验收通过。密钥只写入忽略的项目根`.env`；不要打印展开的`docker compose config`。

## 硅基流动 + BGE-M3

[硅基流动接口](https://siliconflow.readme.io/reference/createembedding)支持`BAAI/bge-m3`及批量字符串；[BAAI官方模型说明](https://huggingface.co/BAAI/bge-m3)记录1024维、多语言和8192 token上下文。使用默认维度，当前适配器不发送降维参数。

```dotenv
EMBEDDING_PROVIDER=openai-compatible
EMBEDDING_API_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=填写你的硅基流动密钥
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_DIMENSIONS=1024
EMBEDDING_REVISION=local-bge-m3-v1
EMBEDDING_BATCH_SIZE=10
EMBEDDING_TIMEOUT_SECONDS=30
SEMANTIC_RELEASE=false
```

revision是本项目部署标签，不是服务商的不可变模型版本；实际模型更新时更换标签、重建并重新验收。batch=10是保守设置，不代表硅基流动的官方上限。适配器自动追加`/embeddings`。

## 阿里云百炼

[百炼文档](https://help.aliyun.com/zh/model-studio/embedding)中的`text-embedding-v4`默认1024维，每请求最多10条文本。设置provider为`openai-compatible`、model为`text-embedding-v4`、dimensions为1024、batch为10；base URL从控制台复制，须与密钥地域匹配。revision使用明确的本地部署标签。

北京地域可复制以下配置到根目录`.env`。将`{WorkspaceId}`替换为控制台的业务空间ID，填写相同地域的API Key；若控制台提供不同Base URL，以控制台为准。程序自动追加`/embeddings`，不要填入DashScope原生接口路径。

```dotenv
EMBEDDING_PROVIDER=openai-compatible
EMBEDDING_API_URL=https://{WorkspaceId}.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
EMBEDDING_API_KEY=填写你的百炼API_Key
EMBEDDING_MODEL=text-embedding-v4
EMBEDDING_DIMENSIONS=1024
EMBEDDING_REVISION=local-bailian-v4-v1
EMBEDDING_BATCH_SIZE=10
EMBEDDING_TIMEOUT_SECONDS=30
SEMANTIC_RELEASE=false
```

地域与业务空间地址依据[官方同步接口说明](https://help.aliyun.com/zh/model-studio/text-embedding-synchronous-api)。保留DeepSeek的CHAT配置；不要覆盖SECRET_KEY、数据库或本地账号配置。

## DeepSeek 问答

[官方更新说明](https://api-docs.deepseek.com/zh-cn/news/news260910/)中的V4.1 Flash使用`deepseek-flash`。可以与上述embedding配置搭配：

```dotenv
CHAT_PROVIDER=openai-compatible
CHAT_API_URL=https://api.deepseek.com
CHAT_API_KEY=填写你的DeepSeek密钥
CHAT_MODEL=deepseek-flash
CHAT_TIMEOUT_SECONDS=60
```

适配器按[官方chat接口](https://api-docs.deepseek.com/api/create-chat-completion/)请求JSON，对官方DeepSeek endpoint设置`reasoning_effort=none`。实际受控响应及最终真实问答已通过，见[验收报告](retrieval-quality-artifacts/release-acceptance.md)。

## 接入后的顺序

2026-10-14：百炼受控batch=2/query=1响应已通过1024维校验；DeepSeek 已配置并完成实际调用与人工审阅。开发集原句8/8、词项8/8、vector/hybrid改写各8/8、独立无关问题20/20为空。检索配置冻结为text-embedding-v4、local-bailian-v4-v1、1024维、batch=10、最低cosine=0.35；profile fingerprint为`340c5e8586b85a9473c8f940bee385108cf146f8522480315c1a98ddca5a8bbe`。见[逐例报告](retrieval-quality-artifacts/dev-bailian-v4-negatives.results.json)。开发负例扩展存为独立`backend/evaluation/corpus-dev-v1.json`，未更改原发布保留集。

1. 核对受控embedding响应的条目index、1024维、finite/nonzero、批量限制及chat结构化响应，不记录密钥。
2. 在独立数据库跑开发集，校准并冻结profile/阈值，最低cosine仍为0.35。override只导入provider配置，数据库仍为独立`quality_test`/tmpfs：

```powershell
docker compose -p campusclaw-quality-real -f docker-compose.retrieval-test.yml -f docker-compose.retrieval-real.yml config --quiet
docker compose -p campusclaw-quality-real -f docker-compose.retrieval-test.yml -f docker-compose.retrieval-real.yml run --build --rm --entrypoint python quality-tests -m evaluation.run --split dev --output /quality-results/dev-real
```

3. 冻结后改为`--split release --output /quality-results/release-real`。未通过退出2（部分Compose版本对外返回1），报告仍保存。不能改发布查询/标签掩盖失败。
4. 逐claim审阅30问答和20反例；补齐真实profile性能、浏览器及schema副本升级/force/resume/回滚报告。未执行的门槛保持incomplete。
5. 备份业务库和uploads，先dry-run再显式重建旧64维演示索引。启动不会对真实服务自动付费全量重建；不同profile不能混合比较。参见[索引操作](retrieval-indexing-operations.md)。
6. 所有门槛通过后才提供匹配profile/chat模型的验收报告并启用semantic release。
