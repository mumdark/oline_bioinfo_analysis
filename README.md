<img width="349" alt="image" src="https://github.com/user-attachments/assets/fad6cd82-632e-48f1-8201-79ad27195091">

# 具体文件夹的内容以该路径的结果为准
```
myproject/
├── myproject/
│   ├── __init__.py
│   ├── settings.py      # 一些初始的设定
│   ├── urls.py          # 定义主路径的路由
│   ├── asgi.py
│   ├── wsgi.py
├── app01/               # 子应用
│   ├── __init__.py
│   ├── admin.py
│   ├── apps.py
│   ├── models.py
│   ├── views.py         # 定义所有的内部操作
│   ├── forms.py
│   ├── urls.py          # 定义子路径的路由
│   ├── templates/       # 定义子应用返回的图形界面
│   │   ├── upload.html
│   │   ├── result.html
│   │   ├── error.html
├── media/               # 生成的结果或储存的文件
│   ├── datafiles/  # 上传的文件将存储在此处
│   ├── result/     # 生成的结果可以储存在这
├── code            # 用于分析的代码
├── manage.py
```

```
pip install django-ninja
django-admin startproject myproject # 创建一个django项目
```

# 创建第一个应用
```
django-admin startapp app01  
```

# 在 INSTALLED_APPS 中添加 app01 和 django_rq
```
import os 
INSTALLED_APPS = [
    ...
    'django_rq',
    'app01',
]

MEDIA_URL = '/media/'
MEDIA_ROOT = os.path.join(BASE_DIR, 'media')

RQ_QUEUES = {
    'default': {
        'HOST': 'localhost',
        'PORT': 6379,
        'DB': 0,
        'DEFAULT_TIMEOUT': 360,
    }
}

LOGGING = {        # 添加debug信息
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'DEBUG',
            'class': 'logging.FileHandler',
            'filename': os.path.join(BASE_DIR, 'debug.log'),
        },
    },
    'loggers': {
        'django': {
            'handlers': ['file'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}
```

# 修改app01/models.py
```
from django.db import models

class DataFile(models.Model):
    name = models.CharField(max_length=255)
    file = models.FileField(upload_to='datafiles/')
    uploaded_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name
```
# 创建app01/forms.py
```
from django import forms
from .models import DataFile

class DataFileForm(forms.ModelForm):
    class Meta:
        model = DataFile
        fields = ['file']
```
# 创建 app01/views.py 定义内部分析过程（需要修改）
```
import os
from django.shortcuts import render, redirect
from django.conf import settings
from .forms import DataFileForm
from .models import DataFile
import django_rq
from rq.job import Job
from rpy2.robjects import r, globalenv
import logging

logger = logging.getLogger('django')

def handle_uploaded_file(f):
    file_path = os.path.join(settings.MEDIA_ROOT, 'datafiles', f.name) # 定义数据路径
    with open(file_path, 'wb+') as destination:  # 以二进制写入模式 ('wb+') 打开文件
        for chunk in f.chunks():                 # 分块读取上传
            destination.write(chunk)
    return file_path

def analyze_data(file_path):
    output_dir = os.path.join(settings.MEDIA_ROOT, 'results')
    os.makedirs(output_dir, exist_ok=True)
    
    # 构建 R 脚本的完整路径
    addgrids3d_path = os.path.join(settings.BASE_DIR, 'code', 'R', '01.addgrids3d.r')
    main_script_path = os.path.join(settings.BASE_DIR, 'code', 'R', '01.3D_UMAP.R')
    
    # 加载 01.addgrids3d.r 脚本
    r.source(addgrids3d_path)
    
    # 加载主 R 脚本 01.3D_UMAP.R
    r.source(main_script_path)
    
    # 调用 R 函数，传递文件路径和输出目录作为参数
    analyze_function = globalenv['analyze_data']
    pdf_file_path = analyze_function(file_path, output_dir)
    
    # 将结果转换为 Python 字符串
    pdf_file_path = str(pdf_file_path)
    return pdf_file_path

# HTTP 是一种用于传输文档的协议，它有多种请求方法，其中最常用的包括 GET 和 POST
# GET 方法：用于从服务器获取数据，常用于请求页面、获取资源等。
# POST 方法：用于向服务器提交数据，常用于提交表单、上传文件、执行操作等
def upload_file(request):
    if request.method == 'POST':
        form = DataFileForm(request.POST, request.FILES)
        if form.is_valid():
            data_file = form.save()
            file_path = handle_uploaded_file(request.FILES['file']) # 使用 handle_uploaded_file 函数处理上传的文件并保存到服务器
            # 打印文件路径以进行调试
            logger.debug(f"Uploaded file path: {file_path}")

            queue = django_rq.get_queue('default')    # 返回 Redis 的 default 默认队列
            job = queue.enqueue(analyze_data, file_path) # 将一个名为 analyze_data 的任务函数推送到刚才获取的 default 队列中，并传递 file_path 作为参数
            return redirect('result', job_id=job.id)    # job.id 由 RQ (Redis Queue) 在任务入队时自动生成。此处，重定向到 result 视图，并传递生成的 job_id
    else:
        form = DataFileForm()
    return render(request, 'upload.html', {'form': form})

def result(request, job_id):
    job = Job.fetch(job_id, connection=django_rq.get_connection())
    if job.is_finished:
        pdf_url = os.path.join(settings.MEDIA_URL, 'results', os.path.basename(job.result))
        result = f"Your analysis is complete. Download the result <a href='{pdf_url}'>here</a>."
    else:
        result = 'Your analysis is in progress...'
    return render(request, 'result.html', {'result': result})
```


# 创建app01/urls.py
```
from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_file, name='upload_file'),
    path('result/<str:job_id>/', views.result, name='result'),
]
```
# 在项目的myproject/urls.py中包含应用的URL
```
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('app01.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
```
# 创建 app01/templates 文件夹，并在其中创建 upload.html 和 result.html
```
## upload.html

<!DOCTYPE html>
<html>
<head>
    <title>Upload File</title>
</head>
<body>
    <h1>Upload File</h1>
    <form method="post" enctype="multipart/form-data">
        {% csrf_token %}
        {{ form.as_p }}
        <button type="submit">Upload</button>
    </form>
</body>
</html>

## result.html
<!DOCTYPE html>
<html>
<head>
    <title>Analysis Result</title>
</head>
<body>
    <h1>Analysis Result</h1>
    <p>{{ result }}</p>
</body>
</html>
```
# 对app/model字段进行了修改，所以需要进行迁移更新
```
python manage.py makemigrations app01
python manage.py migrate
```
# 启动redis-server服务器, D:\Software\Redis
```
D:\Software\Redis\redis-server.exe
```
# 启动RQ worker
```
# pip install rq==1.14  # window系统启动
# pip install git+https://github.com/michaelbrooks/rq-win.git#egg=rq-win  # window系统启动
python manage.py rqworker default # linux系统启动
```
# 运行Django项目
```
python manage.py runserver
```
