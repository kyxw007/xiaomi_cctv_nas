import requests
from webdav3.client import Client
import os
from typing import List, Dict, Optional
import logging
from urllib3.exceptions import HTTPError
from requests.auth import HTTPBasicAuth
import xml.etree.ElementTree as ET

# 配置日志
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

class WebDAVClient:
    def __init__(self, username="kyxw007", password="nb061617"):
        self.server_url = "https://home.kyxw007.wang:5008"
        self.auth = (username, password)
        self.verify_ssl = False  # 忽略SSL证书验证
        self.client = None
        self._connect()

    def _connect(self):
        """建立 WebDAV 连接"""
        if not self.auth[0] or not self.auth[1]:
            raise ValueError("Username and password are required for authentication")

        options = {
            'webdav_hostname': self.server_url,
            'webdav_timeout': 30,
            'webdav_login': self.auth[0],
            'webdav_password': self.auth[1],
            'webdav_root': '/',  # 设置根路径
            'webdav_verbose': True,  # 启用详细日志
        }
        
        logger.debug(f"Connecting to WebDAV server: {self.server_url}")
        logger.debug(f"Using username: {self.auth[0]}")
        
        try:
            self.client = Client(options)
            # 测试连接
            logger.debug("Testing connection with PROPFIND request...")
            response = self._propfind_request('/')
            logger.debug(f"Initial PROPFIND response: {response}")
            logger.info("Successfully connected to WebDAV server")
        except Exception as e:
            logger.error(f"Failed to connect to WebDAV server: {str(e)}")
            raise

    def _propfind_request(self, path: str) -> List[str]:
        """
        发送 PROPFIND 请求获取目录内容
        
        Args:
            path: 要查询的路径
            
        Returns:
            目录内容列表
        """
        # 确保路径以斜杠开头
        if not path.startswith('/'):
            path = '/' + path
            
        url = f"{self.server_url}{path}"
        logger.debug(f"Sending PROPFIND request to: {url}")
        
        headers = {
            'Depth': '1',
            'Content-Type': 'application/xml'
        }
        
        # PROPFIND 请求体
        body = '''<?xml version="1.0" encoding="utf-8" ?>
        <propfind xmlns="DAV:">
            <prop>
                <resourcetype/>
                <getcontentlength/>
                <getlastmodified/>
            </prop>
        </propfind>'''
        
        try:
            response = requests.request('PROPFIND', url, auth=self.auth, headers=headers, data=body, verify=self.verify_ssl)
            response.raise_for_status()
            
            # 解析 XML 响应
            root = ET.fromstring(response.text)
            items = []
            
            # 使用命名空间
            ns = {'D': 'DAV:'}
            
            # 遍历所有响应
            for response in root.findall('.//D:response', ns):
                href = response.find('.//D:href', ns)
                if href is not None:
                    # 获取相对路径
                    path = href.text
                    if path.startswith(self.server_url):
                        path = path[len(self.server_url):]
                    if path.startswith('/'):
                        path = path[1:]
                    items.append(path)
            
            return items
            
        except requests.exceptions.RequestException as e:
            logger.error(f"PROPFIND request failed: {str(e)}")
            raise

    def list_directory(self, remote_path: str = "/") -> List[Dict]:
        """
        列出指定目录下的所有文件和文件夹
        
        Args:
            remote_path: 远程目录路径，默认为根目录
            
        Returns:
            包含文件信息的列表，每个文件信息包含：
            - name: 文件名
            - path: 完整路径
            - type: 类型（'directory' 或 'file'）
        """
        if not self.client:
            raise ConnectionError("WebDAV client not initialized")
            
        try:
            # 确保路径以斜杠结尾
            if not remote_path.endswith('/'):
                remote_path = remote_path + '/'
                
            logger.debug(f"Listing directory: {remote_path}")
            items = self._propfind_request(remote_path)
            logger.debug(f"Raw items list from server: {items}")
            
            if not items:
                logger.warning("Server returned empty list")
                return []
                
            result = []
            
            for item_path in items:
                try:
                    # 移除路径开头的斜杠（如果存在）
                    if item_path.startswith('/'):
                        item_path = item_path[1:]
                        
                    full_path = os.path.join(remote_path, item_path).replace("\\", "/")
                    logger.debug(f"Processing item: {full_path}")
                    
                    # 根据路径末尾是否有斜杠来判断是否为目录
                    is_dir = item_path.endswith('/')
                    
                    result.append({
                        'name': os.path.basename(item_path.rstrip('/')),
                        'path': full_path,
                        'type': 'directory' if is_dir else 'file'
                    })
                except Exception as e:
                    logger.warning(f"Error processing {item_path}: {str(e)}")
                    continue
                
            logger.debug(f"Final result list: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Failed to list directory: {str(e)}")
            raise

    def download_file(self, path: str):
        """下载文件内容
        
        Args:
            path: 文件路径
            
        Returns:
            文件内容的二进制数据，如果下载失败返回None
        """
        try:
            # 使用 requests 直接下载文件
            response = requests.get(
                f"{self.server_url}{path}",
                auth=self.auth,
                verify=self.verify_ssl  # 使用指定的SSL验证
            )
            
            if response.status_code == 200:
                return response.content
            else:
                logger.error(f"Error downloading file {path}: HTTP {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error downloading file {path}: {str(e)}")
            return None

    def stream_file(self, path):
        """流式传输文件内容
        
        Args:
            path: 文件路径
            
        Returns:
            文件内容的生成器，用于流式传输
        """
        try:
            # 使用 requests 流式下载文件
            with requests.get(
                f"{self.server_url}{path}",
                auth=self.auth,
                verify=self.verify_ssl,  # 使用指定的SSL验证
                stream=True    # 启用流式传输
            ) as response:
                if response.status_code == 200:
                    # 使用生成器逐块返回数据
                    for chunk in response.iter_content(chunk_size=8192):  # 8KB chunks
                        if chunk:
                            yield chunk
                else:
                    logger.error(f"Error streaming file {path}: HTTP {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Error streaming file {path}: {str(e)}")
            yield None

# 使用示例
if __name__ == "__main__":
    # 创建客户端实例
    client = WebDAVClient()
    
    # 列出根目录下的所有文件和文件夹
    try:
        items = client.list_directory("/CCTV/")
        if not items:
            print("No items found or no access to any items")
        else:
            print(f"Found {len(items)} items:")
            # 先显示目录，再显示文件
            directories = [item for item in items if item['type'] == 'directory']
            files = [item for item in items if item['type'] == 'file']
            
            if directories:
                print("\nDirectories:")
                for item in directories:
                    print(f"[DIR] {item['name']}")
            
            if files:
                print("\nFiles:")
                for item in files:
                    print(f"[FILE] {item['name']}")
    except Exception as e:
        print(f"Error: {str(e)}") 