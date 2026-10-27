# 解题助手数据升级与回滚

升级在 `initialize_database()` 中完成，版本为 `20261014_tutor_conversations`。新增 tutor_agents、两张绑定表、conversations、messages；既有 skills 通过检查列后逐个添加字段。旧行的ID和名称保留，class_id为空、legacy_placeholder为真、enabled为假，不自动推测其班级。PostgreSQL补充检查约束；SQLite旧表使用同等写入触发器，均有班内名称/种子唯一索引。

`SEED_DEMO_DATA=true` 时，每班数学/语文种子使用幂等键，只创建不存在的配置并绑定相应学科材料；已有教师改动不被覆盖。关闭演示时不创建配置。重复启动不会重复建表或种子。

部署前用项目现有备份流程保存数据库和上传卷，并保留当前api/web镜像标识。升级不重建材料索引、变更embedding profile或改写认证数据。先在专用测试库执行升级两次和回归，再更新api/web；核对登录、材料、原knowledge/ask及新助手。

优先回滚api/web到上一版镜像并停止展示新入口。保留新增表、列、消息和绑定；旧版本忽略这些新增数据，不需要删除或反向迁移。恢复升级前数据库会丢失升级后的写入，只能在明确接受该损失后单独操作，不能作为自动回滚步骤。

验证：`backend/tests/test_tutor_schema.py` 覆盖新schema、旧id/name表升级、重复运行、占位约束、种子不覆盖、非演示启动和材料删除的历史保留；PostgreSQL验证使用隔离测试环境。

2026-10-14隔离演练还使用Git `HEAD` 的上一版后端实际连接升级后的数据库，复用新版本签发的Bearer令牌访问身份、材料、检索和原问答，均返回200；执行前后逐行比较材料、entry、chunk、两类向量、profile、token/session及新增会话消息，全部保持一致。旧版分词器会在源码旁写缓存，验收测试将只读旧源码复制到容器临时目录运行，不修改归档源码或开发库。

可复现命令（先将上一版 `backend/` 解压到忽略的 `.vendor/tutor-previous/backend`）：

```powershell
docker compose -p campusclaw-quality-test -f docker-compose.retrieval-test.yml run --rm --build -e PREVIOUS_BACKEND_DIR=/previous-backend -v E:/Projects/campusclaw-nikke/.vendor/tutor-previous/backend:/previous-backend:ro quality-tests tests -q -p no:cacheprovider
```

挂载源路径替换为本机仓库的绝对路径。`test_tutor_postgres.py`仅接受隔离 `quality_*` 数据库；旧源码目录未配置时回滚项会跳过，不能把跳过计为回滚完成。
