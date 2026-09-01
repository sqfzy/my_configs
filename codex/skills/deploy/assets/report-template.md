# 部署资料包报告：{{title}}

{{summary}}

## 机器基础信息

{{machine}}

### IP、网卡与路由

{{network}}

### CPU 拓扑与业务服务

{{cpu_topology}}

### 内存与磁盘汇总

{{capacity}}

## 代码溯源

{{repositories}}

## 配置

{{configuration}}

## 程序产出

{{program_outputs}}

## 部署变更与健康验证

{{deployment}}

## 部署复现流程

{{reproduce}}

## 回滚流程

{{rollback}}

## 证据说明

- `configured`：来自明确的 systemd 或应用配置。
- `observed`：来自进程、CPU 采样、内核 socket 或路由观测。
- `inferred`：根据启动参数或路由推断，已注明依据。
- `unknown`：证据不足；不会把 DPDK/raw socket 等不可观测路径伪装成确定结果。

> 本资料包是面向可信人员的完整部署交付物。配置原值保存在“配置”章节引用的资料包文件中，包括密码、token、signing secret、证书和私钥；不做脱敏、掩码、哈希、截断或省略。外部状态和数据库不在应用级回滚保证范围内。
