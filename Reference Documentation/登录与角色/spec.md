## Purpose

让教师与学生以各自角色登录 CampusClaw，以班级作为数据边界隔离教学材料；教师上传的内容解析后写入知识库，本班成员通过列表查看；越权上传、跨班访问与未登录访问在服务端被拒绝。

## ADDED Requirements

### Requirement: 用户登录

系统 MUST 提供教师（teacher）、学生（student）两类角色的账号密码登录；登录成功后 MUST 建立服务端会话；未登录用户访问受保护页面 MUST 被引导到登录页，且 MUST NOT 泄露任何业务数据。

#### Scenario: 教师与学生登录成功

- **WHEN** 用户使用有效账号与密码发起登录（预置账号含教师 A、学生 A1、学生 B1）
- **THEN** 登录 MUST 成功并建立服务端会话
- **AND** 会话中 MUST 记录用户标识、角色（teacher 或 student）与所属班级（如班级 A 或 B）

#### Scenario: 错误密码登录失败

- **WHEN** 用户提供存在用户名但错误密码
- **THEN** 登录 MUST 失败
- **AND** 系统 MUST NOT 建立有效会话
- **AND** 响应 MUST NOT 暗示密码哪一位错误以外的敏感信息（如不返回密码哈希）

#### Scenario: 未登录访问受保护页面

- **WHEN** 未携带有效会话的用户请求受保护页面（如材料列表）或受保护 API
- **THEN** 对页面请求 MUST 重定向到登录页
- **AND** 对 API 请求 MUST 返回未授权（如 HTTP 401）
- **AND** 响应 MUST NOT 包含任何本班或他班材料标题、正文或文件路径

### Requirement: 角色权限

系统 MUST 按会话中的角色授权：教师可上传与管理本班材料；学生对本班材料只读；学生调用上传或管理接口 MUST 被拒绝。

#### Scenario: 学生上传被拒绝（403）

- **WHEN** 以 student 角色（如学生 A1）的有效会话向材料上传接口提交文件
- **THEN** 系统 MUST 拒绝请求并返回 HTTP 403（或等价语义的错误码）
- **AND** `materials` 与知识库相关表 MUST 无新增或变更记录
- **AND** 上传目录 MUST 无因该请求产生的新文件（或事务回滚后不可见）

#### Scenario: 教师上传被允许

- **WHEN** 以 teacher 角色（如教师 A）的有效会话向材料上传接口提交支持的文件
- **THEN** 系统 MUST 接受请求并执行入库流程（见「材料上传与知识库入库」）
- **AND** 返回 MUST 表示成功（如 HTTP 201）并含新材料标识

#### Scenario: 学生仅只读本班列表

- **WHEN** 学生 A1 登录后打开本班材料列表
- **THEN** 系统 MUST 展示本班可读材料
- **AND** 页面或 API MUST NOT 提供学生可用的上传或删除本班材料的写操作入口（服务端仍 MUST 拒绝写 API，见上一 Scenario）