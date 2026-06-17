# NLP Evaluation Engine Verification Unit Tests
import sys
import os

# Ensure project root is in python path
sys.path.append(os.path.dirname(__file__))

from app import NLPEvaluator

def test_nlp_evaluator():
    print("Initializing NLPEvaluator...")
    evaluator = NLPEvaluator()

    # Test inputs
    ideal_answer = "Synchronous programming executes operations sequentially, blocking the thread. Asynchronous programming is non-blocking, ideal for I/O bound tasks and network requests."
    keywords = ["sequentially", "non-blocking", "blocking", "I/O bound", "network requests"]

    print("\n--- Running Test Cases ---")

    # 1. Perfect Match Test
    print("\nCase 1: Exact Perfect Match")
    candidate_perfect = "Synchronous programming executes operations sequentially, blocking the thread. Asynchronous programming is non-blocking, ideal for I/O bound tasks and network requests."
    result_perfect = evaluator.evaluate(candidate_perfect, ideal_answer, keywords)
    print(f"Scores -> Correctness: {result_perfect['correctness']}, Relevance: {result_perfect['relevance']}, Completeness: {result_perfect['completeness']}")
    print(f"Feedback -> {result_perfect['feedback']}")
    assert result_perfect['correctness'] >= 90.0, "Perfect match should have high correctness"
    assert result_perfect['completeness'] == 100.0, "All keywords should be present"

    # 2. Similar Match (Rephrased) Test
    print("\nCase 2: Rephrased Similar Answer")
    candidate_similar = "Synchronous executes tasks sequentially and blocks. Asynchronous code is non-blocking and is great for I/O bound network requests."
    result_similar = evaluator.evaluate(candidate_similar, ideal_answer, keywords)
    print(f"Scores -> Correctness: {result_similar['correctness']}, Relevance: {result_similar['relevance']}, Completeness: {result_similar['completeness']}")
    print(f"Feedback -> {result_similar['feedback']}")
    assert result_similar['correctness'] >= 60.0, "Similar rephrased match should be reasonably high"
    assert result_similar['completeness'] >= 80.0, "Most keywords should be matching"

    # 3. Weak / Keyword-Only Match Test
    print("\nCase 3: Weak Keyword-only Answer")
    candidate_weak = "I have used synchronous blocking before, and asynchronous non-blocking."
    result_weak = evaluator.evaluate(candidate_weak, ideal_answer, keywords)
    print(f"Scores -> Correctness: {result_weak['correctness']}, Relevance: {result_weak['relevance']}, Completeness: {result_weak['completeness']}")
    print(f"Feedback -> {result_weak['feedback']}")
    assert result_weak['correctness'] < 60.0, "Weak answer should have moderate correctness"
    assert result_weak['completeness'] < 100.0, "Not all keywords present"

    # 4. Irrelevant / Off-Topic Test
    print("\nCase 4: Completely Irrelevant Answer")
    candidate_irrelevant = "I love to bake chocolate chip cookies in my kitchen during the weekend."
    result_irrelevant = evaluator.evaluate(candidate_irrelevant, ideal_answer, keywords)
    print(f"Scores -> Correctness: {result_irrelevant['correctness']}, Relevance: {result_irrelevant['relevance']}, Completeness: {result_irrelevant['completeness']}")
    print(f"Feedback -> {result_irrelevant['feedback']}")
    assert result_irrelevant['correctness'] < 25.0, "Irrelevant answers should yield low correctness scores"
    assert result_irrelevant['completeness'] == 0.0, "No keywords should match"

    # 5. Empty/Short Answer Test
    print("\nCase 5: Empty / Short Answer")
    candidate_empty = "No."
    result_empty = evaluator.evaluate(candidate_empty, ideal_answer, keywords)
    print(f"Scores -> Correctness: {result_empty['correctness']}, Relevance: {result_empty['relevance']}")
    assert result_empty['correctness'] == 0.0, "Short answers must yield zero scores"

    print("\nAll NLP evaluation test assertions PASSED successfully!")

if __name__ == "__main__":
    test_nlp_evaluator()