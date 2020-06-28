from django.urls import path
from .views import CartAddView,CartInfoView,CartUpdateView,DelCartView,CartDelView
app_name = 'cart'
urlpatterns = [
    path('add', CartAddView.as_view(), name='add'), # 添加购物车
    path('',CartInfoView.as_view(), name='show'),  # 显示购物车
    path('delete',DelCartView.as_view(), name='delete'),  # 显示购物车

    path('update',CartUpdateView.as_view(), name='update'),  # 显示购物车
    path('del',CartDelView.as_view(), name='del'),  # 显示购物车
]
