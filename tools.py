import sys
from io import StringIO
# Lazy import LLM to avoid heavy deps during simple test imports


class Tools:
    """
    Collection of tools for interacting with web pages and executing code.
    Provides methods for page manipulation, JavaScript execution, and Python code evaluation.
    """

    def __init__(self, default_timeout_ms: int = 7000, safe: bool = False):
        """Initialize Tools with LLM instance and defaults.
        
        Args:
            default_timeout_ms: default timeout for Playwright operations
            safe: when true, enforce read-only operations
        """
        self._llm = None
        self.default_timeout_ms = int(default_timeout_ms)
        self.safe = bool(safe)

    # --- JS helpers ---
    def _wrap_js_for_playwright(self, code: str) -> str:
        """Wrap user JS so it is valid for page.evaluate.
        - Avoid bare top-level `return`
        - Prefer arrow function form
        """
        if not isinstance(code, str):
            return code
        stripped = code.strip()
        # If it already looks like a function/arrow/function call, leave as is
        if stripped.startswith("(() =>") or stripped.startswith("() =>") or stripped.startswith("function"):
            return stripped
        # If it starts with return, convert to expression or arrow
        if stripped.startswith("return "):
            expr = stripped[len("return ") :]
            return f"() => {expr}"
        # Simple expression is acceptable as-is
        return stripped

    def execute_js(self, page, js_code: str) -> str:
        """Execute JavaScript code on the page with wrapping and timeout.
        """
        try:
            code = self._wrap_js_for_playwright(js_code)
            return page.evaluate(code, timeout=self.default_timeout_ms)
        except Exception as e:
            return f"JS_ERROR: {e}"

    def _with_retries(self, func, *args, retries: int = 2, **kwargs):
        last_err = None
        for _ in range(retries + 1):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_err = e
        raise last_err

    def click(self, page, css_selector: str) -> str:
        """Click an element on the page (waits for selector)."""
        if self.safe:
            return "SAFE_MODE: click disabled"
        try:
            self._with_retries(page.wait_for_selector, css_selector, timeout=self.default_timeout_ms)
            self._with_retries(page.click, css_selector, timeout=self.default_timeout_ms)
            return page.inner_html("html")
        except Exception as e:
            return f"CLICK_ERROR: {e}"

    def fill(self, page, css_selector: str, value: str) -> str:
        """Fill a form field (waits for selector)."""
        if self.safe:
            return "SAFE_MODE: fill disabled"
        try:
            self._with_retries(page.wait_for_selector, css_selector, timeout=self.default_timeout_ms)
            self._with_retries(page.fill, css_selector, value, timeout=self.default_timeout_ms)
            return page.inner_html("html")
        except Exception as e:
            return f"FILL_ERROR: {e}"

    def submit(self, page, css_selector: str) -> str:
        """Submit a form by clicking an element (waits for selector)."""
        if self.safe:
            return "SAFE_MODE: submit disabled"
        try:
            self._with_retries(page.wait_for_selector, css_selector, timeout=self.default_timeout_ms)
            self._with_retries(page.locator(css_selector).click, timeout=self.default_timeout_ms)
            return page.inner_html("html")
        except Exception as e:
            return f"SUBMIT_ERROR: {e}"

    def presskey(self, page, key: str) -> str:
        """Press a keyboard key.
        
        Args:
            page: Playwright page object
            key: Key to press
            
        Returns:
            Page HTML after key press
        """
        page.keyboard.press(key)
        return page.inner_html("html")

    def goto(self, page, url: str) -> str:
        """Navigate to a URL."""
        try:
            self._with_retries(page.goto, url, timeout=self.default_timeout_ms, wait_until="load")
            return page.inner_html("html")
        except Exception as e:
            return f"GOTO_ERROR: {e}"

    def refresh(self, page) -> str:
        """Refresh the current page."""
        try:
            self._with_retries(page.reload, timeout=self.default_timeout_ms, wait_until="load")
            return page.inner_html("html")
        except Exception as e:
            return f"REFRESH_ERROR: {e}"

    def python_interpreter(self, code: str, page=None) -> str:
        """Execute Python code and capture output (guarded)."""
        if self.safe:
            return "SAFE_MODE: python_interpreter disabled"
        forbidden = ["sync_playwright(", "async_playwright(", "from playwright", "import playwright"]
        if any(f in code for f in forbidden):
            return "PYTHON_ERROR: Playwright launch is not allowed from python_interpreter. Use existing page context."

        output_buffer = StringIO()
        old_stdout = sys.stdout
        sys.stdout = output_buffer
        
        # Make page and browser context available to the executed code
        exec_globals = {'page': page}
        if page:
            exec_globals.update({
                'browser_context': page.context,
                'cookies': page.context.cookies(),
                'current_url': page.url,
                'user_agent': page.evaluate('navigator.userAgent')
            })
        
        try:
            exec(code, exec_globals)
            output = output_buffer.getvalue()
            # Cap output size
            if len(output) > 4000:
                output = output[:4000] + "... [truncated]"
            return output
        except Exception as e:
            return f"PYTHON_ERROR: {e}"
        finally:
            sys.stdout = old_stdout
            output_buffer.close()

    def get_user_input(self, prompt: str) -> str:
        """Get input from user.
        
        Args:
            prompt: Prompt to display to user
            
        Returns:
            Confirmation message
        """
        input(prompt)
        return "Input done!"

    def auth_needed(self) -> str:
        """Prompt for user authentication.
        
        Returns:
            Confirmation message
        """
        input("Authentication needed. Please login and press enter to continue.")
        return "Authentication done!"

    def complete(self) -> str:
        """Mark current task as complete."""
        return "Completed"

    def discover_forms(self, page) -> str:
        """Return JSON with forms and fields discovered on the page."""
        js = """
        () => {
          const out = [];
          document.querySelectorAll('form').forEach((form, idx) => {
            const f = { index: idx, method: (form.method||'GET').toUpperCase(), action: form.action||'', fields: [] };
            form.querySelectorAll('input, select, textarea, button').forEach(el => {
              f.fields.push({
                tag: el.tagName.toLowerCase(),
                type: (el.type||'').toLowerCase(),
                name: el.name||'',
                id: el.id||'',
                placeholder: el.placeholder||'',
                required: !!el.required
              });
            });
            out.push(f);
          });
          return JSON.stringify(out);
        }
        """
        try:
            return page.evaluate(js, timeout=self.default_timeout_ms)
        except Exception as e:
            return f"DISCOVER_FORMS_ERROR: {e}"

    def execute_tool(self, page, tool_use: str):
        """Execute a tool command.
        
        Args:
            page: Playwright page object
            tool_use: Tool command to execute
            
        Returns:
            Result of tool execution or error message
        """
        try:
            return eval("self." + tool_use)
        except Exception as e:
            return f"Error executing tool: {str(e)}"

    def _get_llm(self):
        if self._llm is None:
            from llm import LLM  # local import to avoid test-time dependency
            self._llm = LLM()
        return self._llm

    def extract_tool_use(self, action: str) -> str:
        """Extract tool command from action description.
        
        Args:
            action: Description of action to take
            
        Returns:
            Tool command to execute
        """
        prompt = f"""
            You are an agent who is tasked to build a tool use output based on users plan and action. Here are the tools we can generate. You just need to generate the code, we will run it in an eval in a sandboxed environment.

            ## Tools
            You are an agent and have access to plenty of tools. In your output, you can basically select what you want to do next by selecting one of the tools below. You must strictly only use the tools listed below. Details are given next.

            - execute_js(js_code)
                We are working with python's playwright library and you have access to the page object. You can execute javascript code on the page by passing in the javascript code you want to execute. The execute_js function will simply call the page.evaluate function and get the output of your code. 
                    - Since you are given the request and the response data, if you want to fuzz the API endpoint, you can simply pass in the modified request data and replay the request. Only do this if you are already seeing requests data in some recent conversation.
                    - Remember: when running page.evaluate, we need to return some variable from the js code instead of doing console logs. Otherwise, we can't access it back in python. The backend for analysis is all python.
                    - Playwright uses async functions, just remember that. You know how its evaluate function works, so write code accordingly.
                    - * Important: Our code writing agent often writes very bad code that results in illegal return statements, and other syntax errors around await, async. You should know that we are using playwright.evaluate inside python to evaluate the js code. If you see any errors, fix them before returning the code.
                        - Error often look like execute_js(page, "return _refreshHome('<img src=x onerror=alert(1)>');")
                            Error executing tool: Page.evaluate: SyntaxError: Illegal return statemen
            - click(css_selector)
                If you want to click on a button or link, you can simply pass in the css selector of the element you want to click on.
            - fill(css_selector, value)
                If you want to fill in a form, you can simply pass in the css selector of the element you want to fill in and the value you want to fill in.
            - auth_needed()
                If you are on a page where authentication is needed, simply call this function. We will let the user know to manually authenticate and then we can continue.
            - get_user_input(prompt)
                If you need to get some input from the user, you can simply call this function. We will let the user know to manually input the data and then we can continue. For instance, if you are looking for a username, password, etc, just call this function and ask the user e.g get_user_input("Enter the username: ")
            - presskey(key)
                If you want to press a key, you can simply pass in the key you want to press. This is a playwright function so make sure key works.
            - submit(css_selector)
                If you want to submit a form, you can simply pass in the css selector of the element you want to submit.
            - goto(url)
                If you want to go to a different url, you can simply pass in the url you want to go to.
                If you want to go back to the previous page, you can simply call this function.
            - refresh()
                If you want to refresh the current page, you can simply call this function.
            - python_interpreter(code)
                If you want to run some python code, you can simply pass in the code you want to run. This will be run in a python interpreter and the output will be returned. Do NOT try to launch Playwright here; use the provided `page` context if needed.
                
                IMPORTANT: You can use python_interpreter in two ways:
                1. Standalone: python_interpreter('''import requests; print("hello")''') - use triple quotes
                2. Browser-aware: python_interpreter('''print(current_url); print(len(cookies))''', page)
            - complete()
                If you think you have explored all possible concerns and avenues and we want to move to some other page, you can simply call this function. This will just take whatever next url we have for analysis and go to it.

            ----

            ## Inputs
            Below you are provided a plan and an action. Extract the relevant tool use from the text and only return it without any prefix, sufix, or anything else.

            ```
            {action}
            ```

            ## Output format:
            Your output must exactly be a tool use. For most tools, you must pass the first argument as the page object, and the second argument comes from the action given above. However, python_interpreter() is an exception - it only takes the code parameter. For instance:

            execute_js(page, '() => document.title')
            goto(page, "https://example.com")
            fill(page, "#username", "admin")
            submit(page, "#login")
            python_interpreter('''import requests; print("Hello")''')  # NO page argument!
            python_interpreter('''print(current_url, len(cookies))''', page)  # WITH page for browser context!
            complete() # dont pass in anything
            auth_needed() # dont pass in anything

            Rules:
            - NEVER return bare `return` at top-level JavaScript; prefer `() => expr`
            - Verify selectors exist before click/fill/submit
            - Do not launch Playwright; use provided `page`

            We must not return anything else. Remember that your output is going to be eval'd in a sandboxed environment.
            Remember, no prefixes or suffixes, no ```, no ```python, no ```javascript. Start directly with the actual functions and tools that are given above. I will take care of the rest. Make sure the params to the functions are wrapped in quotes or single quotes, not in backticks. We need to respect the syntax of the language.
        """
        return self._get_llm().output(prompt)
