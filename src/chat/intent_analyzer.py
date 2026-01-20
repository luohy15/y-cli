"""Intent analyzer for smart routing decisions."""

from dataclasses import dataclass
import httpx

from loguru import logger


@dataclass
class RoutingDecision:
    """Smart routing decision"""
    use_think_model: bool       # False = quick, True = think
    use_web_search: bool        # False = no search, True = search
    reasoning_effort: str       # "low", "medium", or "high" (only if use_think_model=True)


class IntentAnalyzer:
    """Uses LLM to analyze user input and decide routing"""

    ANALYSIS_SYSTEM_PROMPT = """You are a routing assistant. Analyze the user's query and decide:
1. Does this need WEB SEARCH? No (0) or Yes (1)?
2. Should this use a QUICK (0) or THINK (1) model?
3. If THINK, what reasoning effort? (low/medium/high)

Use WEB SEARCH (1) when:
- Query mentions "latest", "current", "today", "recent", "2024", "2025"
- Query contains "web search", or explicitly asks to search
- Asking about news, events, or updates
- Needs real-time or very recent information

Use THINK model (1) for:
- Complex reasoning, analysis, or explanations
- Math problems, proofs, or calculations
- Multi-step problems
- Deep technical questions
- Code debugging or optimization

Reasoning effort levels:
- LOW: Simple explanations, basic reasoning
- MEDIUM: Moderate complexity, some analysis needed
- HIGH: Complex proofs, deep analysis, multi-step reasoning

Use QUICK model (0) for:
- Simple questions
- General knowledge
- Basic facts
- Short answers

Response format:
- Quick model: <search>,<model>
- Think model: <search>,<model>,<effort>

Examples:
- "What is Python?" → 0,0
- "Latest AI news?" → 1,0
- "Explain how quicksort works" → 0,1,medium
- "Prove why quicksort is O(n log n)" → 0,1,high
- "Analyze recent quantum breakthroughs" → 1,1,medium
- "What's 2+2?" → 0,1,low"""

    def __init__(self, base_url: str, api_key: str, model: str):
        """Initialize with LLM configuration"""
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    async def _call_llm(self, system_message: str, user_message: str) -> str:
        """Simple LLM call using httpx"""
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://luohy15.com",
                    "X-Title": "y-cli",
                },
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": user_message}
                    ]
                }
            )

            response.raise_for_status()
            result = response.json()
            response_content = result["choices"][0]["message"]["content"]
            # logger.info(f"Analyzer LLM response - Content: {response_content}")
            return response_content

    async def analyze(self, message: str) -> RoutingDecision:
        """Analyze message using LLM and return routing decision"""

        # Call the analyzer model (quick model)
        response_text = await self._call_llm(
            system_message=self.ANALYSIS_SYSTEM_PROMPT,
            user_message=f"Query: {message}"
        )

        # Parse response (e.g., "0,1" or "1,0,high")
        try:
            response_text = response_text.strip()
            parts = response_text.split(',')

            search_choice = int(parts[0].strip())
            model_choice = int(parts[1].strip())

            use_think = model_choice == 1
            use_search = search_choice == 1

            # Extract reasoning effort if present
            reasoning_effort = "medium"  # default
            if use_think and len(parts) >= 3:
                reasoning_effort = parts[2].strip().lower()
                if reasoning_effort not in ["low", "medium", "high"]:
                    reasoning_effort = "medium"

            return RoutingDecision(
                use_think_model=use_think,
                use_web_search=use_search,
                reasoning_effort=reasoning_effort
            )
        except (ValueError, IndexError) as e:
            # Fallback to safe defaults if parsing fails
            logger.warning(f"Parse error, using defaults: {str(e)}")
            return RoutingDecision(
                use_think_model=False,  # Default to quick
                use_web_search=False,
                reasoning_effort="medium"
            )


async def test():
    """Test the intent analyzer with example queries from the design doc"""
    import os
    from dotenv import load_dotenv

    # Load environment variables from .env file
    load_dotenv()

    # Get config from environment variables
    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    analyzer_model = os.getenv("ANALYZER_MODEL", "google/gemini-2.5-flash")

    # Create analyzer
    analyzer = IntentAnalyzer(
        base_url=base_url,
        api_key=api_key,
        model=analyzer_model
    )

    # Test cases from design document with expected results
    # Format: (query, expected_use_think, expected_use_search, expected_effort)
    test_cases = [
        ("What is Python?", False, False, None),
        ("Latest AI news?", False, True, None),
        ("Explain how quicksort works", True, False, "medium"),
        ("Prove why quicksort is O(n log n)", True, False, "high"),
        ("Analyze recent quantum breakthroughs", True, True, "medium"),
        ("What's 2+2?", True, False, "low"),
        # Additional test cases without strict expectations
        ("What's the weather today?", None, True, None),  # Should use search
        ("Solve this integral: ∫x^2 dx", True, None, None),  # Should use think
        ("Tell me a joke", False, None, None),  # Should be quick
        ("Debug this code error: NullPointerException", True, None, None),  # Should use think
    ]

    print(f"\nTesting IntentAnalyzer")
    print(f"Base URL: {base_url}")
    print(f"Analyzer Model: {analyzer_model}\n")
    print("=" * 80)

    passed = 0
    failed = 0

    for query, expected_think, expected_search, expected_effort in test_cases:
        print(f"\nQuery: {query}")
        try:
            decision = await analyzer.analyze(query)

            # Show actual decision
            model_type = "think" if decision.use_think_model else "quick"
            search_status = "yes" if decision.use_web_search else "no"
            if decision.use_think_model:
                print(f"Actual:   Model: {model_type} ({decision.reasoning_effort}), Search: {search_status}")
            else:
                print(f"Actual:   Model: {model_type}, Search: {search_status}")
            print(f"  - Use think model: {decision.use_think_model}")
            print(f"  - Use web search: {decision.use_web_search}")
            if decision.use_think_model:
                print(f"  - Reasoning effort: {decision.reasoning_effort}")

            # Show expected (if defined)
            if expected_think is not None or expected_search is not None:
                expected_parts = []
                if expected_think is not None:
                    expected_parts.append(f"think={expected_think}")
                if expected_search is not None:
                    expected_parts.append(f"search={expected_search}")
                if expected_effort is not None:
                    expected_parts.append(f"effort={expected_effort}")
                print(f"Expected: {', '.join(expected_parts)}")

            # Assertions
            test_passed = True
            if expected_think is not None:
                try:
                    assert decision.use_think_model == expected_think, \
                        f"Expected use_think_model={expected_think}, got {decision.use_think_model}"
                except AssertionError as e:
                    print(f"❌ FAILED: {e}")
                    test_passed = False

            if expected_search is not None:
                try:
                    assert decision.use_web_search == expected_search, \
                        f"Expected use_web_search={expected_search}, got {decision.use_web_search}"
                except AssertionError as e:
                    print(f"❌ FAILED: {e}")
                    test_passed = False

            if expected_effort is not None and decision.use_think_model:
                try:
                    assert decision.reasoning_effort == expected_effort, \
                        f"Expected reasoning_effort={expected_effort}, got {decision.reasoning_effort}"
                except AssertionError as e:
                    print(f"❌ FAILED: {e}")
                    test_passed = False

            if test_passed:
                print("✅ PASSED")
                passed += 1
            else:
                failed += 1

        except Exception as e:
            print(f"❌ ERROR: {e}")
            failed += 1

        print("-" * 80)

    # Summary
    print(f"\n{'=' * 80}")
    print(f"Test Summary: {passed} passed, {failed} failed out of {len(test_cases)} tests")
    print(f"{'=' * 80}")

async def main():
    import os
    from dotenv import load_dotenv

    load_dotenv()

    base_url = os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1")
    api_key = os.getenv("OPENROUTER_API_KEY", "")
    analyzer_model = os.getenv("ANALYZER_MODEL", "google/gemini-3-flash-preview")

    analyzer = IntentAnalyzer(
        base_url=base_url,
        api_key=api_key,
        model=analyzer_model
    )

    query = "hi"
    print(f"Query: {query}")
    decision = await analyzer.analyze(query)
    print(f"Use think model: {decision.use_think_model}")
    print(f"Use web search: {decision.use_web_search}")
    print(f"Reasoning effort: {decision.reasoning_effort}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
