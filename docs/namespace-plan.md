# 统一包名与工具材料迁移

本轮将所有正式 Python 导入统一到 layerweave 下，保留核心、支撑和可替换工具的职责。builtin 与 skills 一起放在包内的 tool 区；examples 留在仓库中，不作为顶层包安装。

## 实施进度

- [x] 核对现有安装、资源路径及迁移范围。
- [x] 迁移源码、工具、默认配置和示例，更新导入与类路径。
- [x] 配置资源打包和技能安装位置，重新安装开发环境。
- [x] 更新文档、命令示例和测试目录引用。
- [x] 验证同名模块冲突、普通安装、技能资源及工具隔离。
- [x] 完整回归与示例验证，审查后提交推送。

## 约定

- src/layerweave 下保留 core、models/layers、models/objects、support 和 tool/builtin、tool/skills。
- 默认 configs 随包携带，保留 layers、objects、logging 分区；数据库 config_ref 仍相对于配置根目录，不改记录格式。
- 只安装 layerweave 顶层包，不提供 core/models/support/tool/examples 的旧导入转接。
- skills 是文件材料，完整保留说明、脚本和附件。内置命令发现仅扫描 builtin。
- 开发源码可直接维护自带材料；ZIP 默认写入当前工作目录的 tool/skills，也可用已有 skills_root 明确指定目录。普通安装不默认写入库目录。
- 核心与支撑不自动加载工具，完整工具包仍可单独增减。
- 测试使用临时库，保留 output 数据与已有 scratch 材料；迁移先预检并保留可回退证据。

## 验收重点

1. 宿主目录同时有 core.py、models.py、support.py、tool.py、examples.py 时，公开导入、实例保存和还原仍成功。
2. 在干净环境普通安装 wheel 后，读取默认 TOML、schema.sql 和自带 SKILL.md/脚本成功；不借用源码目录。
3. wheel 仅暴露 layerweave，示例、测试、scratch 和旧包名不进入正式安装。
4. 沿用无工具和单工具包隔离验收，并执行完整回归和全部示例。

## 验收结果

- 完整回归 372 项：371 项通过，1 项因 Windows 符号链接权限跳过。
- 宿主中五种同名文件和同名包均通过公开导入、实例保存/还原、工具及技能调用验收；宿主模块保持原样。
- 普通 wheel 仅声明 layerweave 顶层包；24 份配置、SQL 与技能资源和源码逐文件一致。
- wheel 无网络、无依赖安装到临时目标后，在禁用 site 的新进程中完成验证，不使用可编辑源码回退；26 个命令可用。
- 无工具支撑与 10 个完整工具包的隔离验收通过，15 个 examples 脚本全部运行成功。
- 现有数据库格式和 config_ref 保持不变；Python 导入、TOML class、CLI 与技能示例路由已同步。
