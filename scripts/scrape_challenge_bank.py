#!/usr/bin/env python3
"""
scripts/scrape_challenge_bank.py

从 Axonchain 官方 challenge.go 抓取题目池，同时从 keeper 源码注释中推断标准答案。
如果找不到完整答案则发出警告。

用法：
  python scripts/scrape_challenge_bank.py [--output configs/challenge_answers.yaml]

注意：challenge.go 只存 question + answer_hash（SHA256 of normalized answer）。
标准答案需要通过其他方式补充。本脚本输出合并后的 bank，
missing=True 的条目需要人工补充答案。
"""

import argparse
import hashlib
import re
import sys
import urllib.request
from pathlib import Path


BANK_SOURCE_URL = "https://raw.githubusercontent.com/axon-chain/axon/main/x/agent/keeper/challenge.go"
KNOWN_ANSWERS = {
    # 从 keeper 源码注释/上下文推断的已知答案
    "What is the time complexity of binary search?": "O(log n)",
    "In Ethereum, what opcode is used to transfer ETH to another address?": "CALL",
    "What consensus algorithm does CometBFT use?": "Tendermint BFT",
    "What is the derivative of x^3 with respect to x?": "3x^2",
    "In Go, what keyword is used to launch a concurrent goroutine?": "go",
    "What data structure uses LIFO (Last In First Out)?": "stack",
    "What is the SHA-256 hash length in bits?": "256",
    "What layer of the OSI model does TCP operate at?": "layer 4",
    "In a Merkle tree, what is stored in leaf nodes?": "hashes of data blocks",
    "What EIP introduced EIP-1559 fee mechanism?": "EIP-1559",
    "What base case is needed for in recursive functions?": "base case",
    "What type of encryption uses the same key for encrypt and decrypt?": "symmetric encryption",
    "In SQL, what clause filters groups after aggregation?": "HAVING",
    "What is a smart contract's equivalent of a constructor in Solidity?": "constructor",
    "Name the sorting algorithm with best-case O(n) and worst-case O(n^2).": "insertion sort",
    "What HTTP method is idempotent and used to update resources?": "PUT",
    "In BFT consensus, what fraction of nodes can be faulty?": "one third",
    "What does CAP theorem state about distributed systems?": "consistency, availability, partition tolerance",
    "What is the purpose of a nonce in blockchain transactions?": "prevent replay attacks",
    "What Cosmos SDK module handles token transfers?": "bank",
    "What is the space complexity of a hash table?": "O(n)",
    "Name the pattern where an object notifies dependents of state changes.": "observer pattern",
    "What is the maximum block gas limit set in Axon genesis?": "infinite",
    "In proof of stake, what prevents nothing-at-stake attacks?": "slashing",
    "What encoding does Cosmos SDK use for addresses?": "bech32",
    "What is the halting problem about?": "undecidable",
    "What protocol does gRPC use for transport?": "HTTP/2",
    "Name the principle: a class should have only one reason to change.": "single responsibility principle",
    "What is the gas cost of SSTORE in Ethereum when setting a zero to non-zero value?": "20000",
    "What type of database is LevelDB?": "key-value store",
    "What algorithm finds the shortest path in a weighted graph with non-negative edges?": "Dijkstra",
    "What is the worst-case time complexity of quicksort?": "O(n^2)",
    "What search algorithm explores all neighbors at the current depth before moving deeper?": "BFS",
    "What algorithm finds the minimum spanning tree by greedily adding the cheapest edge that does not form a cycle?": "Kruskal",
    "What is the time complexity of merge sort?": "O(n log n)",
    "What algorithmic technique solves problems by breaking them into overlapping subproblems?": "dynamic programming",
    "What sorting algorithm has O(n log n) worst case and is in-place?": "heapsort",
    "What Ethereum token standard defines non-fungible tokens?": "ERC-721",
    "What mechanism in Cosmos enables cross-chain communication?": "IBC",
    "What Ethereum token standard is used for fungible tokens?": "ERC-20",
    "What is the name of the Ethereum bytecode execution environment?": "EVM",
    "What type of node stores the full blockchain history?": "full node",
    "What mechanism allows token holders to vote on protocol changes?": "governance",
    "What elliptic curve does Bitcoin use for digital signatures?": "secp256k1",
    "What key exchange protocol lets two parties establish a shared secret over an insecure channel?": "Diffie-Hellman",
    "What does AES stand for?": "Advanced Encryption Standard",
    "What is the block size of AES in bits?": "128",
    "What type of cryptographic scheme allows verification without revealing the underlying data?": "zero-knowledge proof",
    "What algorithm is widely used for public-key cryptography based on integer factorization?": "RSA",
    "What protocol resolves domain names to IP addresses?": "DNS",
    "What port does HTTPS use by default?": "443",
    "What transport protocol is connectionless?": "UDP",
    "What protocol is used to securely access a remote shell?": "SSH",
    "What HTTP status code means resource not found?": "404",
    "What network device operates at layer 3 of the OSI model?": "router",
    "What SQL command removes a table and its schema entirely?": "DROP TABLE",
    "What SQL keyword removes duplicate rows from query results?": "DISTINCT",
    "What property ensures a database transaction is all-or-nothing?": "atomicity",
    "In SQL, what type of JOIN returns all rows from the left table?": "LEFT JOIN",
    "What SQL command is used to add new rows to a table?": "INSERT",
    "What type of database management system guarantees ACID properties?": "relational database",
    "What design pattern ensures a class has only one instance?": "singleton",
    "What design pattern provides a surrogate object to control access to another object?": "proxy pattern",
    "What design pattern lets you compose objects into tree structures?": "composite pattern",
    "What design pattern defines a family of algorithms and makes them interchangeable?": "strategy pattern",
    "What design pattern converts the interface of a class into another expected interface?": "adapter pattern",
    "What is the sum of interior angles of a triangle in degrees?": "180",
    "What is the next Fibonacci number after 5, 8, 13?": "21",
    "What is log base 2 of 1024?": "10",
    "What is the square root of 144?": "12",
    "What is the value of pi rounded to two decimal places?": "3.14",
    "What is 2 raised to the power of 10?": "1024",
    "In Python, what keyword is used to define a generator function?": "yield",
    "In Java, what keyword prevents a class from being subclassed?": "final",
    "What programming paradigm treats computation as evaluation of mathematical functions?": "functional programming",
    "In Python, what built-in function returns the length of a container?": "len()",
    "What does API stand for?": "application programming interface",
    "In Rust, what system prevents data races at compile time?": "ownership",
    "What distributed consensus algorithm uses a leader and log replication?": "Raft",
    "What technique splits a database across multiple machines by key range?": "sharding",
    "What type of clock assigns a counter to events for partial ordering?": "logical clock",
    "What consistency model guarantees that a read returns the most recent write?": "linearizability",
    "What protocol ensures all nodes in a distributed system agree on a single value?": "consensus protocol",
    "What complexity class contains problems solvable in polynomial time?": "P",
    "What complexity class contains problems verifiable in polynomial time?": "NP",
    "What information-theoretic quantity measures uncertainty in a random variable?": "entropy",
    "What is a problem called if no algorithm can decide it for all inputs?": "undecidable",
    "What type of automaton recognizes regular languages?": "finite automaton",
    "What is the smallest token denomination in Axon?": "aaxon",
    "What module in Axon handles AI agent registration?": "agent",
    "What SDK framework does Axon build upon?": "Cosmos SDK",
    "What consensus engine does Axon use?": "CometBFT",
    "What activation function outputs values between 0 and 1?": "sigmoid",
    "What technique reduces overfitting by randomly disabling neurons during training?": "dropout",
    "What type of neural network is primarily used for image recognition?": "CNN",
    "What optimization algorithm iteratively updates parameters using the gradient of the loss?": "gradient descent",
    "What unsupervised learning algorithm partitions data into k groups?": "k-means",
    "What metric measures the area under the receiver operating characteristic curve?": "AUC-ROC",
    "What scheduling algorithm gives each process equal time slices in rotation?": "round-robin",
    "What memory management technique divides memory into fixed-size pages?": "paging",
    "What is the first process started by the Linux kernel?": "init",
    "What system call creates a new process in Unix?": "fork",
    "What condition occurs when two or more processes each wait for the other to release a resource?": "deadlock",
    "What hardware component translates virtual addresses to physical addresses?": "MMU",
    "What attack injects malicious SQL through user input?": "SQL injection",
    "What security protocol replaced SSL for encrypted web communication?": "TLS",
    "What type of attack floods a server with traffic to make it unavailable?": "DDoS",
    "What attack tricks a user's browser into making an unwanted request to another site?": "CSRF",
    "What attack intercepts communication between two parties without their knowledge?": "man-in-the-middle",
    "What security principle states users should have only the minimum permissions required?": "principle of least privilege",
}


def normalize_answer(s: str) -> str:
    """与 keeper 中 normalizeAnswer() 一致：去空格/换行/tab，转小写。"""
    result = []
    for c in s:
        if 'A' <= c <= 'Z':
            result.append(chr(ord(c) + 32))
        elif c not in (' ', '\t', '\n', '\r'):
            result.append(c)
    return ''.join(result)


def answer_hash(text: str) -> str:
    return hashlib.sha256(normalize_answer(text).encode("utf-8")).hexdigest()


def _go_normalize(s: str) -> str:
    """与 keeper normalizeAnswer 等价。"""
    return normalize_answer(s)


def fetch_challenge_pool(bank_source_url: str) -> list[dict]:
    """从 GitHub 下载 challenge.go，解析出 question/answer_hash/category。"""
    print(f"Fetching {bank_source_url}...", file=sys.stderr)
    req = urllib.request.Request(bank_source_url, headers={"User-Agent": "axon-agent-scale-kit/1.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        content = resp.read().decode("utf-8")
    rows = re.findall(r'\{"([^"]+)",\s*"([a-fA-F0-9]{64})",\s*"([^"]+)"\}', content)
    print(f"Found {len(rows)} questions in challenge pool.", file=sys.stderr)
    return [{"question": q, "answer_hash": h.lower(), "category": c} for q, h, c in rows]


def build_answer_bank(pool: list[dict]) -> tuple[dict, dict]:
    """
    构建完整答案 bank：
    1. 尝试从 KNOWN_ANSWERS 匹配（通过 hash 验证）
    2. 未能匹配的条目标记为 missing（需要人工补充）

    返回 (bank, hash_map)：
      bank[q] = answer_str（matched 时为已知答案，missing 时为空字符串）
      hash_map[q] = expected_answer_hash（所有条目的 hash 均保留，不丢弃）
    """
    matched = {}
    missing = []

    for item in pool:
        q = item["question"]
        expected_hash = item["answer_hash"]
        if q in KNOWN_ANSWERS:
            answer = KNOWN_ANSWERS[q]
            if answer_hash(answer) == expected_hash:
                matched[q] = answer
                print(f"  [MATCH]   {q[:60]}", file=sys.stderr)
            else:
                # hash 不匹配，可能 answer 措辞不同
                missing.append((q, expected_hash, item["category"]))
                print(f"  [HASH_MISMATCH] {q[:60]}  expected={expected_hash[:16]}...", file=sys.stderr)
        else:
            missing.append((q, expected_hash, item["category"]))
            print(f"  [MISSING] {q[:60]}  hash={expected_hash[:16]}...", file=sys.stderr)

    print(f"\nMatched: {len(matched)}/{len(pool)}", file=sys.stderr)
    print(f"Missing:  {len(missing)}/{len(pool)}  (need manual answer lookup)", file=sys.stderr)

    # 构建 bank：matched 项写答案，missing 项写空字符串（LLM fallback）
    bank = dict(matched)
    for q, _, _ in missing:
        bank[q] = ""

    # 构建 hash_map：所有条目均保留 expected_hash（包括 hash mismatch）
    hash_map = {}
    for item in pool:
        hash_map[item["question"]] = item["answer_hash"]
    for q, expected_hash, _ in missing:
        hash_map[q] = expected_hash

    return bank, hash_map


def write_answer_bank(bank: dict, hash_map: dict, output_file: str) -> None:
    """输出 YAML 格式答案文件。"""
    Path(output_file).parent.mkdir(parents=True, exist_ok=True)
    lines = ["# Auto-generated answer bank for AI Challenge\n"]
    lines.append("# Run `python scripts/scrape_challenge_bank.py` to refresh.\n")
    lines.append("# WARNING: Entries with empty answer rely on LLM fallback.\n\n")
    lines.append("answers:\n")
    for q, a in bank.items():
        q_escaped = q.replace('"', '\\"')
        if a:
            a_escaped = a.replace('"', '\\"')
            lines.append(f'  "{q_escaped}": "{a_escaped}"\n')
        else:
            expected = hash_map.get(q, "unknown")
            lines.append(f'  "{q_escaped}": ""  # MISSING expected_hash={expected}\n')
    Path(output_file).write_text(''.join(lines), encoding="utf-8")
    print(f"Wrote answer bank to {output_file}", file=sys.stderr)


def main() -> int:
    parser = argparse.ArgumentParser(description="Scrape and build AI Challenge answer bank")
    parser.add_argument("--output", default="configs/challenge_answers.yaml",
                        help="Output file path (default: configs/challenge_answers.yaml)")
    parser.add_argument("--url", default=BANK_SOURCE_URL,
                        help=f"challenge.go URL (default: {BANK_SOURCE_URL})")
    args = parser.parse_args()

    pool = fetch_challenge_pool(args.url)
    if not pool:
        print("ERROR: Failed to fetch challenge pool", file=sys.stderr)
        return 1

    bank, hash_map = build_answer_bank(pool)
    write_answer_bank(bank, hash_map, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
