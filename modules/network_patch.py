import os
import socket
import requests
from requests.adapters import HTTPAdapter
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import psutil
except ImportError:
    psutil = None

class SourceAddressAdapter(HTTPAdapter):
    def __init__(self, source_address, **kwargs):
        self.source_address = source_address
        super().__init__(**kwargs)

    def init_poolmanager(self, *args, **kwargs):
        kwargs['source_address'] = (self.source_address, 0)
        return super().init_poolmanager(*args, **kwargs)

def get_physical_ipv4():
    """查找本地真实的物理网卡 IPv4 地址 (排除虚拟网卡、回环网卡、TUN/TAP 网卡)"""
    if not psutil:
        return None
    candidate = None
    try:
        for iface, addrs in psutil.net_if_addrs().items():
            iface_lower = iface.lower()
            if any(bad in iface_lower for bad in ['tun', 'tap', 'loopback', 'vethernet', 'wsl', 'vmware', 'virtual']):
                continue
            for a in addrs:
                if a.family == socket.AF_INET:
                    ip = a.address
                    if not ip.startswith('127.') and not ip.startswith('169.254.'):
                        if 'wlan' in iface_lower or 'wi-fi' in iface_lower or '以太网' in iface_lower or 'ethernet' in iface_lower:
                            return ip
                        candidate = ip
    except Exception:
        pass
    return candidate

def apply_network_patch():
    """
    全局网络直连补丁：
    1. 域名劫持绕过 TUN/Fake-IP: 将 api.moguding.net 直连解析到国内阿里云真实 IP 118.190.120.71
    2. 物理网卡源地址绑定: 自动绑定物理 WLAN/网卡 IP，绕过 TUN 路由
    3. 环境变量与系统代理绕过: 禁用 requests 继承系统代理
    """
    os.environ['NO_PROXY'] = '*'
    
    # 1. 劫持 DNS 解析
    _orig_getaddrinfo = socket.getaddrinfo
    def patched_getaddrinfo(host, port, *args, **kwargs):
        if host == 'api.moguding.net':
            return _orig_getaddrinfo('118.190.120.71', port, *args, **kwargs)
        return _orig_getaddrinfo(host, port, *args, **kwargs)
    socket.getaddrinfo = patched_getaddrinfo

    # 2. 查找物理 IP
    phy_ip = get_physical_ipv4()
    if phy_ip:
        print(f"[NET_PATCH] 已绑定物理网卡 IP ({phy_ip})，全量直连国内工学云服务器")

    # 3. 增强 requests.Session
    orig_session_init = requests.Session.__init__
    def new_session_init(self, *args, **kwargs):
        orig_session_init(self, *args, **kwargs)
        self.trust_env = False
        if phy_ip:
            self.mount('http://', SourceAddressAdapter(phy_ip))
            self.mount('https://', SourceAddressAdapter(phy_ip))
    requests.Session.__init__ = new_session_init
