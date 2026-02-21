# Metrics: Offline Evaluation Framework

## Goal

Define a repeatable offline evaluation loop for RAG quality before release.

## Scope

- End-to-end answer quality (correctness, completeness, faithfulness)
- Retrieval/search quality (hit rate, ranking quality, context relevance)

## Evaluation Dataset

- Build a versioned benchmark set with representative user queries
- Include simple, multi-hop, and ambiguous questions
- Maintain gold references for expected answers and/or supporting documents

## Core Metrics

- End-to-end:
  - Accuracy
  - Groundedness/Faithfulness
  - Refusal correctness
- Search:
  - Recall@K
  - MRR/NDCG
  - Context precision
- Operational:
  - Latency per query
  - Token cost per query

## Baseline and Comparison

- Establish a fixed baseline run before major architecture changes
- Compare candidate changes against baseline with delta reporting

## Execution Plan

- Run full offline evaluation in CI for major PRs
- Run lightweight smoke evaluation on every commit
- Publish results to dashboard/artifact for trend tracking

## Acceptance Criteria

- No regression on key metrics versus baseline
- End-to-end accuracy and Recall@K meet agreed thresholds
- Failures are categorized by cause:
  - Retrieval miss
  - Reasoning error
  - Formatting/tool error

