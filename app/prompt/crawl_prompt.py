from aiohttp_retry import Callable


CRAWL_CONTENT_FILTER_PROMPT:Callable[[str,list[str]],str] = lambda focus,include:"""
"""