# 部署简报：{{title}}

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

## 关键配置

{{key_config}}

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

> 报告不包含密钥、token、密码、私钥或 webhook secret。外部状态和数据库不在应用级回滚保证范围内。
