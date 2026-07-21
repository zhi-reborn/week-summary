# Linux 原生安装与运维

## 支持范围与目录

- x86-64、glibc、systemd Linux；Debian/Ubuntu 使用 `.deb`，RHEL 兼容发行版使用通用 `tar.gz`。
- 目标机不需要 Docker、Python 或 Node.js。
- 程序：`/opt/weekly-report-assistant`
- 数据：`/var/lib/weekly-report-assistant`
- 日志：`/var/log/weekly-report-assistant/app.jsonl`
- 配置：`/etc/weekly-report-assistant/environment`

服务以无登录权限的 `weekly-report` 用户运行，只监听 `127.0.0.1:8765`。

## Debian/Ubuntu

```bash
sudo dpkg -i dist/installers/weekly-report-assistant_0.1.0_amd64.deb
curl http://127.0.0.1:8765/api/health/ready
```

重新安装新版本 `.deb` 即可升级。迁移程序会在数据库版本变化前生成 SQLite 一致性备份。
如果 `postinst` 的迁移或 readiness 失败，脚本会停止服务并恢复迁移前的数据，但不会覆盖
dpkg 管理的程序文件；软件包将保持“未配置”状态。修复原因后重新安装当前包，或明确安装上一版本包，不能把失败状态视为升级成功。

## 通用 tar.gz

```bash
tar -xzf weekly-report-assistant-0.1.0-linux-x64.tar.gz
cd weekly-report-assistant-0.1.0
sudo ./install.sh
```

`install.sh` 会检查 root、x86-64、systemd、端口占用，并支持重复执行。安装失败时会恢复旧程序、数据库和 systemd 单元。

默认卸载保留业务数据：

```bash
sudo /opt/weekly-report-assistant/installer/uninstall.sh
```

tar 包中的 `uninstall.sh --purge` 会额外删除数据、日志、配置和服务账户。对于 deb 包，`dpkg -r` 默认保留 `/etc` 配置与 `/var/lib` 数据。

## 服务检查与安全沙箱

```bash
systemctl status weekly-report-assistant.service
journalctl -u weekly-report-assistant.service -n 100
systemd-analyze security weekly-report-assistant.service
curl http://127.0.0.1:8765/health
curl http://127.0.0.1:8765/api/health/ready
```

单元启用了 `NoNewPrivileges`、`PrivateTmp`、`ProtectSystem=strict`、`ProtectHome`、空 capability 集合，并仅放行数据与日志目录写权限。

## 原生验证记录

当前开发环境为 macOS，不能生成或安装 Linux ELF/deb。下表必须在 Linux x86-64 构建机和干净 VM 上执行脚本后填写。

| 系统 | 安装方式 | 结果 |
|---|---|---|
| Debian 12 x86-64 | deb | 未验证 |
| Ubuntu 22.04/24.04 x86-64 | deb | 未验证 |
| RHEL 9 兼容 x86-64 | tar.gz | 未验证 |
