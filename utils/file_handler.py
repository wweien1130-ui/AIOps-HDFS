import os
import hashlib

from langchain_core.documents import Document

import utils

from utils.logger_handler import logger
from langchain_community.document_loaders import PyPDFLoader,TextLoader,WebBaseLoader,DirectoryLoader

def get_file_md5_hex(filename:str):
    if not os.path.exists(filename):
        logger.error(f"[md5计算]文件{filename}不存在")
        return None

    if not os.path.isfile(filename):
        logger.error(f"[md5计算]路径{filename}不是文件")
        return None

    md5_obj = hashlib.md5()

    chunk_size = 4096

    try:
        with open(filename,"rb") as f:
            while chunk := f.read(chunk_size):
                md5_obj.update(chunk)

        mdg_hex = md5_obj.hexdigest()
        return mdg_hex
    except Exception as e:
        logger.error(f"[md5计算]文件{filename}读取失败:{e}")
        return None


def listdir_with_allowed_type(path:str,allowed_types:tuple[str]):
    files =[]

    if not os.path.isdir(path):
        logger.error(f"[listdir_with_allowed_type]路径{path}不是文件夹")
        return tuple()

    for f in os.listdir(path):
        if f.endswith(allowed_types):
            files.append(os.path.join(path,f))

    return tuple(files)


def pdf_loader(filepath:str,passwd=None)->list[Document]:
    return PyPDFLoader(filepath,passwd).load()

def txt_loader(filepath:str)->list[Document]:
    return TextLoader(filepath,encoding="utf-8").load()
