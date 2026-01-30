import json
from llm import LLM
from pathlib import Path
from datetime import datetime

class Reporter:
    """
    Security vulnerability reporter that analyzes findings and generates reports.
    
    Analyzes conversation history between security testing agent and target system
    to validate discovered vulnerabilities and generate detailed reports.
    """

    def __init__(self, starting_url, output_dir: str = "security_results"):
        """
        Initialize the reporter.

        Args:
            starting_url: Base URL that was tested
        """
        self.llm = LLM()
        self.reports = []
        self.starting_url = starting_url
        self.output_dir = Path(output_dir)
        self.filename = str(self.starting_url).replace("https://", "").replace("http://", "").replace("/", "_")

    def generate_safe_crawl_summary(self, proxy, forms_json: str = "[]", include_third_party: bool = False, export_csv: bool = False):
        """
        Generate read-only crawl artifacts (JSON and Markdown) from proxy data.
        This avoids LLM usage and only summarizes observed GET traffic and forms.
        """
        out_dir = self.output_dir / "safe_crawl"
        out_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        base = f"{self.filename}_{ts}"

        # Collect URLs and endpoints from proxy
        net = proxy.get_network_data()
        requests = net.get('requests', [])
        responses = net.get('responses', [])
        pairs = net.get('pairs', [])

        from urllib.parse import urlparse, urldefrag
        start_host = urlparse(self.starting_url).netloc

        def same_origin(u: str) -> bool:
            try:
                return urlparse(u).netloc == start_host
            except Exception:
                return False

        def canon(u: str) -> str:
            try:
                u2, _ = urldefrag(u)
                return u2
            except Exception:
                return u

        urls_all = [r.get('url') for r in requests if r.get('url')]
        if not include_third_party:
            urls_all = [u for u in urls_all if same_origin(u)]
        visited_urls = sorted({canon(u) for u in urls_all})

        xhr_fetch = [r for r in requests if r.get('resource_type') in ('xhr','fetch')]
        ep_urls = [r.get('url') for r in xhr_fetch if r.get('url')]
        if not include_third_party:
            ep_urls = [u for u in ep_urls if same_origin(u)]
        js_endpoints = sorted({canon(u) for u in ep_urls})
        blocked_count = len([1 for r in responses if isinstance(r.get('status'), int) and r['status'] == 0 and 'SAFE_MODE' in str(r)])

        # Aggregate response headers (top N by frequency)
        header_counts = {}
        for res in responses:
            hdrs = res.get('headers', {}) or {}
            for k in hdrs.keys():
                k_low = k.lower()
                header_counts[k_low] = header_counts.get(k_low, 0) + 1
        common_headers = sorted(header_counts.items(), key=lambda x: x[1], reverse=True)[:15]

        data = {
            "target": self.starting_url,
            "generated_at": ts,
            "visited_urls": visited_urls,
            "js_endpoints": js_endpoints,
            "forms_json": forms_json,
            "common_response_headers": common_headers,
            "blocked_non_get_attempts": blocked_count,
        }

        # Write JSON
        json_path = out_dir / f"{base}.json"
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        # Write quick Markdown
        md_path = out_dir / f"{base}.md"
        md = [
            f"# Safe Crawl Summary - {self.starting_url}",
            f"Generated: {ts}",
            "",
            "## Visited URLs", *[f"- {u}" for u in visited_urls[:200]],
            "",
            "## JS Endpoints (XHR/Fetch)", *[f"- {u}" for u in js_endpoints[:200]],
            "",
            "## Forms (JSON)",
            f"```json\n{forms_json}\n```",
            "",
            "## Common Response Headers",
            *[f"- {k}: {cnt}" for k,cnt in common_headers],
            "",
            f"Blocked non-GET attempts: {blocked_count}",
        ]
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("\n".join(md))

        # Optional CSV exports for pipelines
        if export_csv:
            import csv, json as _json
            # endpoints.csv
            with open(out_dir / f"{base}_endpoints.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["url"])
                for u in js_endpoints:
                    w.writerow([u])
            # forms.csv
            try:
                forms = _json.loads(forms_json)
            except Exception:
                forms = []
            with open(out_dir / f"{base}_forms.csv", "w", newline="", encoding="utf-8") as f:
                w = csv.writer(f)
                w.writerow(["form_index","method","action","field_tag","field_type","name","id","placeholder","required"])
                for form in (forms or []):
                    idx = form.get('index')
                    method = form.get('method')
                    action = form.get('action')
                    for fld in form.get('fields', []):
                        w.writerow([
                            idx, method, action,
                            fld.get('tag'), fld.get('type'), fld.get('name'), fld.get('id'), fld.get('placeholder'), fld.get('required')
                        ])

    def report(self, history):
        """
        Analyze conversation history to validate if a real vulnerability was found.

        Uses strict criteria to evaluate if the conversation demonstrates a proven,
        exploitable vulnerability versus theoretical or low-severity issues.

        Args:
            history: List of conversation messages between agent and system

        Returns:
            Tuple of (bool, str) indicating if exploit was successful and detailed report
        """
        system_prompt = f"""
        You are a highly critical security vulnerability judge. Your job is to analyze a conversation between a security testing agent and determine if a REAL, WORKING exploit was actually discovered and proven.

        You must be extremely strict in your assessment. For a vulnerability to be considered valid, the conversation MUST show:
        1. A clear attack vector that was successfully exploited
        2. Concrete proof that the exploit worked (e.g. actual sensitive data accessed, actual code execution achieved, authentication bypass, privilege escalation, etc.)
        3. Specific technical details about how the exploit was performed
        4. The exact payload/steps that made it work

        You must REJECT findings that:
        - Are theoretical or potential vulnerabilities without proof
        - Only show error messages or unexpected behavior
        - Lack a working proof-of-concept exploit
        - Are low severity issues like mixed content, missing headers etc.
        - Make assumptions about what "could" be possible
        - Don't have explicit evidence of successful exploitation

        If and ONLY if you see clear evidence of a working exploit, create a brief report with:
        - Description of the proven vulnerability
        - The exact endpoint/component affected
        - The specific payload/steps that worked
        - Evidence showing successful exploitation
        
        For instance, if we have found a CSRF issue, is the endpoint actually an authentication endpoint? Is it sensitive? Similarly, if we have found an XSS issue, can the user really control that input? If there is a js engine inside the page and we can get an alert, that's not an issue at all. Vulnerabilities are rare, so you need to be extremely strict in your examination.

        A good criteria you can use is that if we submit it to hackerone, do we get a bounty of more than $1000? If so, it's probably a valid issue. But you rarely get that, right?!

        Remember: Your job is to eliminate false positives. Be extremely skeptical and demanding of proof.
        """

        system_prompt = [{"role": "system", "content": system_prompt}]
        history.append({"role": "user", "content": "Please analyze our conversation history and determine if any vulnerabilities were definitively proven with working exploits, or if the agent was just working lazily and stopped prematurely."})
        report = self.llm.reason(system_prompt + history)

        successful_exploit = self.parse_report(report)

        # Save reports as they are generated
        if successful_exploit:
            self.reports.append(report)
            self.save_reports()
        
        return successful_exploit, report

    def parse_report(self, report):
        """
        Parse a vulnerability report to determine if exploit was successful.

        Args:
            report: String containing the vulnerability report

        Returns:
            bool indicating if report demonstrates successful exploit
        """
        system_prompt = f"""
        You are a report parser whose task is to look at a report and its evaluation and return a boolean value indicating whether the report resulted in a successful exploit or not.

        Only return 1 word, either "yes" if the report resulted in a successful exploit or "no" if it did not.
        """

        system_prompt = [{"role": "system", "content": system_prompt}]
        response = self.llm.reason(system_prompt + [{"role": "user", "content": report}])
        response = str(response)
        return "yes" in response

    def save_reports(self):
        """Save all vulnerability reports to a text file."""
        report_path = self.output_dir / f"{self.filename}.txt"
        with open(report_path, "w") as f:
            f.write("\n\n-------\n\n".join(self.reports))

    def generate_summary_report(self):
        """
        Generate a comprehensive markdown summary of all findings.
        
        Reads all previously saved reports and creates a well-formatted markdown
        document summarizing the vulnerabilities found, their severity, and
        technical details.
        """
        # Load all reports from file
        try:
            report_path = Path("security_results") / f"{self.filename}.txt"
            with open(report_path, "r") as f:
                report_content = f.read()
        except FileNotFoundError:
            report_content = "No vulns were reported."

        system_prompt = f"""
        You are a security report summarizer. Your task is to analyze the security findings and create a comprehensive markdown summary report.

        For each vulnerability found:
        1. Provide a clear description of the vulnerability and its severity
        2. Detail the affected endpoint/component
        3. Include the exact payload/steps that were used to exploit it
        4. Document the proof/evidence that confirmed successful exploitation
        5. Explain potential impact and recommendations

        Format the output as a proper markdown document with:
        - Executive summary at the top
        - Table of contents
        - Detailed findings in separate sections
        - Technical details in code blocks
        - Clear headings and structure
        
        Focus on proven vulnerabilities with concrete evidence. Exclude theoretical or unproven issues.
        """

        system_prompt = [{"role": "system", "content": system_prompt}]
        summary = self.llm.reason(system_prompt + [{"role": "user", "content": report_content}])
        # Save markdown summary report
        self.output_dir.mkdir(parents=True, exist_ok=True)
        with open(self.output_dir / f"{self.filename}_summary.md", "w") as f:
            f.write(summary)
