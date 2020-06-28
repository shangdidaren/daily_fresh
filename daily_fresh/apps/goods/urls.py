from django.conf.urls import url
from django.urls import path
from .views import IndexView, DetailView, ListView
app_name = 'goods'
urlpatterns = [
    path('index', IndexView.as_view(), name='index') , # 为了做区分，nginx的调度
    path('goods/<int:goods_id>', DetailView.as_view(), name = 'detail'),
    path('list/<int:type_id>/<page>', ListView.as_view(), name='list'),
   # url(r'^list/(?P<type_id>\d+)/(?P<page>\d+)$', ListView.as_view(), name='list'),

]
