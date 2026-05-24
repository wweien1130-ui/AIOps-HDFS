import os.path

from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter


from utils.file_handler import txt_loader,pdf_loader,listdir_with_allowed_type,get_file_md5_hex
from utils.config_handler import chroma_config
from model.factory import embedding_models
from utils.path_tool import get_abs_path

from utils.logger_handler import logger

class VectorStoreService:
    def __init__(self):
        self.vector_store = Chroma(
            collection_name = chroma_config["database"]["collection_name"],
            embedding_function=embedding_models,
            persist_directory=chroma_config["database"]["persist_directory"]
        )
        self.spliter = RecursiveCharacterTextSplitter(
            chunk_size=chroma_config["performance"]["batch_size"],
            chunk_overlap=chroma_config["performance"]["batch_overlap"],
            separators=chroma_config["performance"]["separators"],
            length_function=len
        )

    def get_retriever(self):
        return self.vector_store.as_retriever(search_kwargs={"k":chroma_config["performance"]["k"]})

    def load_document(self):

        def check_md5_hex(md5_for_check:str):
            if not os.path.exists(get_abs_path(chroma_config["performance"]["md5_hex_store"])):
                open(get_abs_path(chroma_config["performance"]["md5_hex_store"]), "w",encoding="utf-8").close()
                return False

            with open(get_abs_path(chroma_config["performance"]["md5_hex_store"]), "r",encoding="utf-8") as f:
                for line in f.readlines():
                    line = line.strip()
                    if line == md5_for_check:
                        return True

                return False

        def save_md5_hex(md5_for_check:str):
            with open(get_abs_path(chroma_config["performance"]["md5_hex_store"]), "a",encoding="utf-8") as f:
                f.write(md5_for_check+"\n")

        def get_file_documents(read_path:str):
            if read_path.endswith(".txt"):
                return txt_loader(read_path)
            elif read_path.endswith(".pdf"):
                return pdf_loader(read_path)
            return []
        

        # 读取 hdfs_knowledge/ 目录下的文件

        allowed_files_path:list[str] = listdir_with_allowed_type(
            get_abs_path(chroma_config["performance"]["data_path"]),  # ← hdfs_knowledge
            tuple(chroma_config["performance"]["allow_knowledge_file_type"])  # ← .txt, .pdf
        )

        for path in allowed_files_path:
            md5_hex = get_file_md5_hex(path)
            if check_md5_hex(md5_hex):
                logger.info(f"[加载知识库]{path}内容已经存在知识库内，跳过加载")
                continue

            try:

                 # 1. 加载文档
                documents:list[Document] = get_file_documents(path)

                if not documents:
                    logger.warning(f"[加载知识库]{path}内容为空，跳过加载)")
                    continue
                # 2. 分割文本
                split_documents:list[Document] = self.spliter.split_documents(documents)

                if not split_documents:
                    logger.warning(f"[加载知识库]{path}内容分割为空，跳过加载)")
                    continue
                # 3. 存入向量数据库
                self.vector_store.add_documents(split_documents)

                save_md5_hex(md5_hex)

                logger.info(f"[加载知识库]{path}内容加载完成")
            except Exception as e:
                logger.error(f"[加载知识库]{path}内容加载失败:{e}")
                continue

