import os
from django.shortcuts import render, redirect
from django.conf import settings
from .forms import DataFileForm
from .models import DataFile
import django_rq
from rq.job import Job
from rpy2.robjects import r, globalenv
import logging
import re

logger = logging.getLogger('django')

def handle_uploaded_file(f):
    file_path = os.path.join(settings.MEDIA_ROOT, 'datafiles', f.name) # 定义数据路径
    with open(file_path, 'wb+') as destination:  # 以二进制写入模式 ('wb+') 打开文件
        for chunk in f.chunks():                 # 分块读取上传
            destination.write(chunk)
    return file_path

def delete_file(file_path):            # 定义删除函数的数据
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            print(f"File {file_path} has been deleted successfully.")
        else:
            print(f"File {file_path} does not exist.")
    except Exception as e:
        print(f"Error occurred while deleting the file: {e}")

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
            delete_file(file_path)            # 删除上传的数据
            return redirect('result', job_id=job.id)    # job.id 由 RQ (Redis Queue) 在任务入队时自动生成。此处，重定向到 result 视图，并传递生成的 job_id
    else:
        form = DataFileForm()
    return render(request, 'upload.html', {'form': form})

def result(request, job_id):
    queue = django_rq.get_queue('default')
    job = queue.fetch_job(job_id)
    if job is None:
        return render(request, 'error.html', {'message': 'Job not found.'})

    if job.is_finished:
        result = job.result
        match = re.search(r'\"(.+?)\"', result)
        if match:
            actual_path = match.group(1)
        else:
            actual_path = result
        
        if actual_path.startswith("E:"):
            relative_path = os.path.relpath(actual_path, settings.MEDIA_ROOT)
            relative_path = os.path.join(settings.MEDIA_URL, relative_path)#.replace('\\', '/')
        else:
            relative_path = actual_path
    elif job.is_failed:
        result = f"Job failed with error: {job.exc_info}"
        relative_path = None
    else:
        result = 'Job is still running...'
        relative_path = None

    return render(request, 'result.html', 
                  {'result': actual_path, 
                   'image_path': relative_path,
                   })