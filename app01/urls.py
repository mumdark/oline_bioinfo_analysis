from django.urls import path
from . import views

urlpatterns = [
    path('', views.upload_file, name='upload_file'),      # 路由模式匹配根URL,将会匹配并调用views.upload_file视图
    path('result/<str:job_id>/', views.result, name='result'), # 这个路由模式匹配result/后面跟一个字符串参数job_id的URL，这个模式将会匹配并调用views.result视图，同时将some_job_id作为参数传递给该视图
]