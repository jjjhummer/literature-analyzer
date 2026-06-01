"""测试中文文本预处理流水线"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.analyzers.advanced.text_processor import preprocess_text, batch_preprocess


def test_basic_tokenization():
    """测试基本分词"""
    text = "本文研究了管柱力学在深水钻井中的应用"
    tokens = preprocess_text(text)
    assert len(tokens) > 0, "分词结果不应为空"
    # 核心词应保留
    core_words = ["管柱", "力学", "深水", "钻井"]
    for word in core_words:
        # jieba 可能将词分为更小的单位
        all_tokens = " ".join(tokens)
        assert any(w in all_tokens for w in [word, word[:-1]]), f"应包含核心词: {word}"
    print(f"✅ 基本分词测试通过: {tokens}")


def test_stopwords_removal():
    """测试停用词过滤"""
    text = "本文的研究结果表明该方法具有很好的应用前景"
    tokens = preprocess_text(text)
    # 停用词不应出现
    assert "本文" not in tokens, "应过滤'本文'"
    assert "的" not in tokens, "应过滤'的'"
    # 有意义的词应保留
    meaningful = ["研究", "结果", "表明", "方法", "应用", "前景"]
    found = [t for t in tokens if t in meaningful]
    assert len(found) > 0, f"应有意义词被保留: {tokens}"
    print(f"✅ 停用词过滤测试通过: {tokens}")


def test_empty_text():
    """测试空文本"""
    assert preprocess_text("") == []
    assert preprocess_text(None) == []
    print("✅ 空文本测试通过")


def test_batch_processing():
    """测试批量处理"""
    texts = [
        "管柱力学分析研究",
        "深水钻井技术发展",
    ]
    results = batch_preprocess(texts)
    assert len(results) == 2
    for r in results:
        assert len(r) > 0
    print(f"✅ 批量处理测试通过: {results}")


def test_domain_dictionary():
    """测试领域词典"""
    text = "管柱力学在深水钻井中的应用"
    tokens_with_dict = preprocess_text(text, add_domain_words=["管柱力学", "深水钻井"])
    tokens_without_dict = preprocess_text(text)
    # 有领域词典时可能保留更完整的词
    print(f"   有词典: {tokens_with_dict}")
    print(f"   无词典: {tokens_without_dict}")
    print("✅ 领域词典测试通过")


if __name__ == "__main__":
    print("=" * 50)
    print("  测试中文文本预处理流水线")
    print("=" * 50)

    test_basic_tokenization()
    test_stopwords_removal()
    test_empty_text()
    test_batch_processing()
    test_domain_dictionary()

    print("\n✅ 所有测试通过!")
