"""
知识库导入脚本
将 CSV 知识库文件导入 Chroma 向量数据库

使用方法:
    python backend/import_knowledge.py

    或者指定文件:
    python backend/import_knowledge.py --files data/knowledge_1.csv data/knowledge_2.csv data/knowledge_3.csv
"""
import os
import sys
import argparse
from typing import List

# 添加 backend 目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from chroma_client import ChromaClient
from csv_loader import CSVKnowledgeBaseLoader, MultiCSVKnowledgeBaseLoader
from embedding import EmbeddingService
from utils import logger


def find_csv_files(directory: str = "data") -> List[str]:
    """查找目录下的所有 knowledge_*.csv 文件"""
    import glob
    pattern = os.path.join(directory, "knowledge_*.csv")
    return sorted(glob.glob(pattern))


def import_knowledge_files(
    csv_files: List[str],
    batch_size: int = 50
) -> dict:
    """
    导入 CSV 知识库文件到 Chroma

    Args:
        csv_files: CSV 文件路径列表
        batch_size: 批量向量化和导入的批次大小

    Returns:
        导入结果统计
    """
    chroma_client = ChromaClient()
    embedding_service = EmbeddingService()

    results = {
        'total_files': len(csv_files),
        'total_records': 0,
        'imported_records': 0,
        'by_file': {}
    }

    print(f"\n{'='*60}")
    print(f"开始导入 {len(csv_files)} 个 CSV 知识库文件")
    print(f"{'='*60}\n")

    for csv_path in csv_files:
        if not os.path.exists(csv_path):
            print(f"[跳过] 文件不存在：{csv_path}")
            continue

        filename = os.path.basename(csv_path)
        source_name = filename.replace('.csv', '')

        print(f"\n[处理] {filename}...")

        try:
            # 1. 加载 CSV
            loader = CSVKnowledgeBaseLoader(csv_path)
            docs = loader.load()
            print(f"  加载了 {len(docs)} 条记录")

            if not docs:
                print(f"  [警告] 没有读取到数据")
                continue

            # 2. 分批处理（避免一次性向量化太多）
            total_imported = 0

            for i in range(0, len(docs), batch_size):
                batch_end = min(i + batch_size, len(docs))
                batch_docs = docs[i:batch_end]

                # 提取内容并获取向量
                contents = [doc.page_content for doc in batch_docs]
                print(f"  正在向量化批次 [{i+1}-{batch_end}]...")
                embeddings = embedding_service.get_embeddings(contents)

                # 生成唯一 ID
                ids = [
                    f"{source_name}_{doc.metadata.get('record_id', i+i)}"
                    for i, doc in enumerate(batch_docs)
                ]
                metadatas = [doc.metadata for doc in batch_docs]

                # 导入到 Chroma
                count = chroma_client.add_knowledge_records(
                    source_name=source_name,
                    ids=ids,
                    embeddings=embeddings,
                    metadatas=metadatas,
                    documents=contents
                )

                total_imported += count
                print(f"  导入 {count} 条记录")

            # 统计结果
            results['total_records'] += len(docs)
            results['imported_records'] += total_imported
            results['by_file'][filename] = {
                'loaded': len(docs),
                'imported': total_imported,
                'collection': f"knowledge_{source_name}"
            }

            print(f"  [完成] 共导入 {total_imported}/{len(docs)} 条记录")

        except Exception as e:
            print(f"  [错误] {e}")
            import traceback
            traceback.print_exc()
            results['by_file'][filename] = {
                'error': str(e)
            }

    return results


def print_summary(results: dict):
    """打印导入摘要"""
    print(f"\n{'='*60}")
    print("导入摘要")
    print(f"{'='*60}")
    print(f"文件总数：{results['total_files']}")
    print(f"记录总数：{results['total_records']}")
    print(f"成功导入：{results['imported_records']} 条")

    print(f"\n按文件统计:")
    for filename, stats in results['by_file'].items():
        if 'error' in stats:
            print(f"  {filename}: 错误 - {stats['error']}")
        else:
            print(f"  {filename}:")
            print(f"    加载：{stats['loaded']} 条")
            print(f"    导入：{stats['imported']} 条")
            print(f"    集合：{stats['collection']}")

    print(f"\n{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(description="导入 CSV 知识库到 Chroma")
    parser.add_argument(
        "--files",
        nargs="+",
        help="CSV 文件路径列表"
    )
    parser.add_argument(
        "--directory",
        default="data",
        help="CSV 文件所在目录 (默认：data)"
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=50,
        help="批量处理大小 (默认：50)"
    )

    args = parser.parse_args()

    # 确定要导入的文件
    if args.files:
        csv_files = args.files
    else:
        csv_files = find_csv_files(args.directory)
        if not csv_files:
            print(f"[错误] 在目录 {args.directory} 下未找到 knowledge_*.csv 文件")
            sys.exit(1)

    print(f"发现以下 CSV 文件:")
    for f in csv_files:
        print(f"  - {f}")

    # 执行导入
    results = import_knowledge_files(csv_files, batch_size=args.batch_size)

    # 打印摘要
    print_summary(results)

    # 验证导入结果
    print("验证导入结果:")
    chroma_client = ChromaClient()
    for collection in chroma_client.list_knowledge_collections():
        # 获取集合记录数
        source_name = collection.replace("knowledge_", "", 1)
        count = chroma_client.get_knowledge_count(source_name)
        print(f"  {collection}: {count} 条记录")


if __name__ == "__main__":
    main()
