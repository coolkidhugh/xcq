# 写春秋企业管理咨询AI应用部署指南

## 项目概述

这是一个为写春秋企业管理咨询公司开发的AI驱动咨询应用，集成了案例库管理和AI对话功能。应用已经过生产环境适配，添加了密码保护功能，并准备好进行永久部署。

## 部署到Render.com

### 准备工作

1. 创建Render.com账户
2. 创建新的Web Service
3. 连接GitHub仓库或直接上传代码

### 部署步骤

1. **创建新的Web Service**
   - 选择"Web Service"
   - 选择代码来源（GitHub或直接上传）
   - 名称设置为"xieqiuqiu-consultant"

2. **配置部署设置**
   - 构建命令: `pip install -r requirements.txt`
   - 启动命令: `gunicorn app:app`
   - 环境变量:
     - `PYTHON_VERSION`: `3.11.0`
     - `ACCESS_PASSWORD`: `xiechunqiu`

3. **配置自定义域名**
   - 在Render.com控制台中选择"Custom Domains"
   - 添加自定义域名
   - 按照DNS配置说明设置域名解析

4. **SSL证书配置**
   - Render.com会自动为自定义域名提供免费的SSL证书
   - 证书会自动续期，无需手动操作

### 数据持久化

Render.com提供持久化磁盘存储，确保应用数据不会在部署间丢失：

1. 在Web Service设置中启用"Disk"
2. 设置挂载路径为`/app/data`
3. 确保应用中的数据路径与挂载路径一致

## 本地测试

在部署到Render.com之前，可以在本地测试应用：

```bash
cd web-deploy
pip install -r requirements.txt
python app.py
```

访问 http://localhost:5000 并使用密码"xiechunqiu"登录。

## 访问应用

部署完成后，可以通过以下方式访问应用：

1. Render.com提供的默认域名: `https://xieqiuqiu-consultant.onrender.com`
2. 配置的自定义域名

## 安全注意事项

1. 密码保护已启用，访问密码为"xiechunqiu"
2. 所有API端点都受密码保护
3. 应用使用HTTPS加密通信
4. 定期备份数据目录
