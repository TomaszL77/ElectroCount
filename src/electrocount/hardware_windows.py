"""Read-only Windows hardware probes. No WMI, shell commands or model downloads."""
import ctypes as c
import os
import platform
import uuid


def memory_status():
    if os.name != "nt":
        return {"total_ram_mb": None, "available_ram_mb": None}
    class Memory(c.Structure):
        _fields_ = [("length",c.c_uint32),("load",c.c_uint32)] + [(name,c.c_uint64) for name in
            ("total","available","page_total","page_available","virtual_total","virtual_available","extended")]
    value = Memory(); value.length = c.sizeof(value)
    if not c.windll.kernel32.GlobalMemoryStatusEx(c.byref(value)):
        return {"total_ram_mb": None, "available_ram_mb": None}
    return {"total_ram_mb": round(value.total/2**20), "available_ram_mb": round(value.available/2**20)}


def process_memory():
    if os.name != "nt":
        return {"working_set_mb": None, "peak_working_set_mb": None}
    class Counters(c.Structure):
        _fields_ = [("cb",c.c_uint32),("faults",c.c_uint32)] + [(n,c.c_size_t) for n in
            ("peak","working","peak_paged","paged","peak_nonpaged","nonpaged","pagefile","peak_pagefile")]
    value = Counters(); value.cb = c.sizeof(value)
    kernel = c.WinDLL("kernel32",use_last_error=True)
    kernel.GetCurrentProcess.restype = c.c_void_p
    psapi = c.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [c.c_void_p,c.c_void_p,c.c_uint32]
    if not psapi.GetProcessMemoryInfo(kernel.GetCurrentProcess(),c.byref(value),value.cb):
        return {"working_set_mb": None, "peak_working_set_mb": None}
    return {"working_set_mb": round(value.working/2**20,1), "peak_working_set_mb": round(value.peak/2**20,1)}


def cpu_info():
    result = {"name":platform.processor() or "Unknown", "logical_cores":os.cpu_count() or 1, "physical_cores":None}
    if os.name != "nt":
        return result
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
            result["name"] = winreg.QueryValueEx(key,"ProcessorNameString")[0].strip()
        kernel = c.WinDLL("kernel32",use_last_error=True)
        count = c.c_uint32()
        kernel.GetLogicalProcessorInformationEx(0,None,c.byref(count))
        buffer = c.create_string_buffer(count.value)
        if kernel.GetLogicalProcessorInformationEx(0,buffer,c.byref(count)):
            offset = cores = 0
            while offset + 8 <= count.value:
                size = c.c_uint32.from_buffer(buffer,offset+4).value
                if size < 8 or offset+size > count.value:
                    break
                cores += 1; offset += size
            result["physical_cores"] = cores or None
    except (OSError, AttributeError):
        pass
    return result


def dll_available(name):
    if os.name != "nt":
        return False
    try:
        c.WinDLL(name)
        return True
    except OSError:
        return False


def gpu_info():
    if os.name != "nt":
        return [], "DXGI available only on Windows"
    class GUID(c.Structure):
        _fields_ = [("bytes",c.c_ubyte*16)]
    def guid(text):
        return GUID((c.c_ubyte*16).from_buffer_copy(uuid.UUID(text).bytes_le))
    class Desc(c.Structure):
        _fields_ = [("description",c.c_wchar*128),("vendor",c.c_uint32),("device",c.c_uint32),
            ("subsystem",c.c_uint32),("revision",c.c_uint32),("dedicated",c.c_size_t),
            ("system",c.c_size_t),("shared",c.c_size_t),("luid_low",c.c_uint32),
            ("luid_high",c.c_int32),("flags",c.c_uint32)]
    def method(pointer,slot,result,*args):
        address = c.cast(pointer,c.POINTER(c.POINTER(c.c_void_p))).contents[slot]
        return c.WINFUNCTYPE(result,c.c_void_p,*args)(address)
    factory = c.c_void_p()
    adapters = []
    try:
        library = c.WinDLL("dxgi")
        create = library.CreateDXGIFactory1
        create.argtypes = [c.POINTER(GUID),c.POINTER(c.c_void_p)]
        create.restype = c.c_int32
        iid = guid("770aae78-f26f-4dba-a829-253c83d1b387")
        if create(c.byref(iid),c.byref(factory)) < 0:
            return [], "CreateDXGIFactory1 failed"
        enum = method(factory,12,c.c_int32,c.c_uint32,c.POINTER(c.c_void_p))
        for index in range(16):
            adapter = c.c_void_p()
            if enum(factory,index,c.byref(adapter)) < 0:
                break
            try:
                desc = Desc()
                if method(adapter,10,c.c_int32,c.POINTER(Desc))(adapter,c.byref(desc)) < 0 or desc.flags & 2:
                    continue
                dx12 = False
                if dll_available("d3d12"):
                    d3d = c.WinDLL("d3d12")
                    d3d.D3D12CreateDevice.argtypes = [c.c_void_p,c.c_uint32,c.POINTER(GUID),c.c_void_p]
                    d3d.D3D12CreateDevice.restype = c.c_int32
                    device_iid = guid("189819f1-1db6-4b57-be54-1821339b85f7")
                    dx12 = d3d.D3D12CreateDevice(adapter,0xb000,c.byref(device_iid),None) >= 0
                adapters.append({"name":desc.description,"vendor_id":desc.vendor,
                    "vendor":{0x10de:"NVIDIA",0x1002:"AMD",0x8086:"Intel"}.get(desc.vendor,"Other"),
                    "dedicated_vram_mb":round(desc.dedicated/2**20),"shared_memory_mb":round(desc.shared/2**20),
                    "directx12":dx12})
            finally:
                method(adapter,2,c.c_uint32)(adapter)
        return adapters, ""
    except (OSError,AttributeError) as exc:
        return adapters, str(exc)
    finally:
        if factory:
            method(factory,2,c.c_uint32)(factory)


def cuda_info():
    if not dll_available("nvcuda"):
        return {"available":False,"devices":0,"reason":"CUDA driver unavailable"}
    try:
        driver = c.WinDLL("nvcuda")
        count,version = c.c_int(),c.c_int()
        if driver.cuInit(0) != 0 or driver.cuDeviceGetCount(c.byref(count)) != 0:
            return {"available":False,"devices":0,"reason":"CUDA driver initialization failed"}
        driver.cuDriverGetVersion(c.byref(version))
        return {"available":count.value>0,"devices":count.value,"driver_api_version":version.value}
    except (OSError,AttributeError) as exc:
        return {"available":False,"devices":0,"reason":str(exc)}
