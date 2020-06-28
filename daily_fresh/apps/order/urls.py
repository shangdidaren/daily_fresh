from django.urls import path, include
from order.views import OrderPlaceView, OrderCommitView,\
    OrderPayView, CheckPayView, CommentView


app_name = 'order'
urlpatterns = [
    path('place', OrderPlaceView.as_view(), name='place'),
    path('commit', OrderCommitView.as_view(), name='commit'),  # 创建订单
    path('pay', OrderPayView.as_view(), name='pay'),  # 创建订单

    path('check', CheckPayView.as_view(), name='check'),  # 检查订单
    path('comment/<order_id>', CommentView.as_view(), name='comment')  # 检查订单

]
