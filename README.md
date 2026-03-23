# 招标信息日报系统

每天自动采集招标信息，生成网页，分享链接给领导即可查看。

## 部署步骤（10分钟完成）

### 第一步：上传文件到 GitHub

1. 登录 github.com，点右上角 **"+"** → **New repository**
2. 仓库名填：`tender-daily`，选 **Public**（必须公开才能用 GitHub Pages）
3. 点 **Create repository**
4. 把本压缩包解压，将所有文件上传到仓库

上传后仓库应包含：
```
scraper.py
requirements.txt
.github/workflows/daily.yml
README.md
```

### 第二步：开启 GitHub Pages

1. 进入仓库 → 点 **Settings**
2. 左侧找 **Pages**
3. Source 选 **Deploy from a branch**
4. Branch 选 **gh-pages**，文件夹选 **/ (root)**
5. 点 **Save**

### 第三步：手动触发第一次采集

1. 进入仓库 → 点 **Actions** 标签
2. 左侧点 **每日招标信息采集**
3. 右侧点 **Run workflow** → **Run workflow**
4. 等待约 2 分钟，绿色 ✓ 表示成功

### 第四步：获取你的专属网页地址

格式为：
```
https://你的用户名.github.io/tender-daily/
```

例如用户名是 `zhangsan`，地址就是：
```
https://zhangsan.github.io/tender-daily/
```

把这个链接发给领导，他们打开就能看到最新招标日报！

## 之后每天全自动

- 每天北京时间 **12:00** 自动运行
- 数据来自**中国政府采购网**等官方平台
- 采集完自动更新网页，领导刷新即可看到最新数据

## 常见问题

**Q：Actions 运行失败怎么办？**
点进去看红色报错，截图发给我帮你排查。

**Q：网页能分享给多少人？**
无限制，任何人用链接都能访问。

**Q：数据更新频率？**
每天一次，也可以在 Actions 页面手动触发。
