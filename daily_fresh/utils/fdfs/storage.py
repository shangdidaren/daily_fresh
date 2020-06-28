from django.core.files.storage import Storage
from django.conf import settings
from fdfs_client.client import Fdfs_client


class FDFSStorage(Storage):
    def _open(self, name, mode='rb'):
        pass

    def __init__(self, client_conf=None, base_url=None):
        '''如果没有传入值，就必须能以无参数的形式实例化存储系统'''
        if client_conf is None:
            self.client_conf = settings.FDFS_CLIENT_CONF
        else:
            self.client_conf = client_conf

        if base_url is None:
            self.base_url = settings.FDFS_URL
        else:
            self.base_url = base_url

    def _save(self, name, content):
        '''保存文件时使用'''
        # name 是你上传的文件的名字
        # 包含你上传文件内容的File对象

        # 创建一个对象
        client = Fdfs_client(self.client_conf)
        # 上传到fdfs文件系统中  按照文件内容上传
        res = client.upload_by_buffer(content.read())

        # 返回的字典形式，可以在Fdfs_client函数中找到
        # dict {
        #             'Group name'      : group_name,
        #             'Remote file_id'  : remote_file_id,
        #             'Status'          : 'Upload successed.',
        #             'Local file name' : local_file_name,
        #             'Uploaded size'   : upload_size,
        #             'Storage IP'      : storage_ip
        #         }
        if res.get('Status') != 'Upload successed.':
            # 上传失败
            raise Exception('上传到fdfs失败')

        # 获取返回的文件id
        filename = res.get('Remote file_id')

        return filename

    def exists(self, name):
        '''django判断文件名是否可用'''
        '''重写这个方法，因为在fdfs中所有的文件名都是可用的，但是经过django，django会判断，所以要重写他'''
        return False

    def url(self, name):
        '''返回文件的url路径'''
        return self.base_url + name
