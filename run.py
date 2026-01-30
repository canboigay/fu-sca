import argparse
import os
import warnings
from agent import Agent

def main():
    # Suppress known noisy third-party warnings (accuracy unaffected)
    warnings.filterwarnings(
        "ignore",
        message=r"Core Pydantic V1 functionality isn't compatible with Python 3.14 or greater",
    )
    banner = """
    ╔══════════════════════════════════════════════════════════════════════╗
    ║                                                                      ║
    ║                  Rogue - LLM Powered Security Scanner                ║
    ║                                                                      ║
    ║           Automated Penetration Testing with LLM Intelligence        ║
    ║                                                                      ║
    ║     [+] Intelligent vulnerability discovery                          ║
    ║     [+] Advanced payload generation                                  ║
    ║     [+] Context-aware testing                                        ║
    ║     [+] Automated exploit verification                               ║
    ║                                                                      ║
    ║                -- Happy hunting, use responsibly! --                 ║
    ║                                                                      ║
    ╚══════════════════════════════════════════════════════════════════════╝
    """
    
    parser = argparse.ArgumentParser(
        description='AI-Powered Web Application Security Testing Agent',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
    # Quick security assessment (5 plans, 3 iterations each)
    python run.py -u https://example.com -p 5 -i 3

    # Standard comprehensive scan (10 plans, 10 iterations)
    python run.py -u https://example.com -p 10 -i 10

    # Unlimited plans with contextual CVE intelligence (15-25+ plans)
    python run.py -u https://example.com -p -1 -i 5

    # Deep security audit with scope expansion
    python run.py -u https://example.com -p -1 -i 10 -e -s

    # Targeted research with advanced model
    python run.py -u https://example.com -p 20 -i 15 -m o1-preview

    # Custom output directory with subdomain enumeration
    python run.py -u https://example.com -s -o "results/$(date +%Y%m%d)" -p -1
        '''
    )
    
    parser.add_argument('-u', '--url', 
                        required=True,
                        help='Target URL to test')

    parser.add_argument('-e', '--expand',
                        action='store_true',
                        default=False,
                        help='Expand testing to discovered URLs')
    
    parser.add_argument('-s', '--subdomains',
                        action='store_true',
                        default=False,
                        help='Perform subdomain enumeration')

    parser.add_argument('-m', '--model',
                        choices=['o3-mini', 'o1-preview', 'o4-mini'],
                        default='o4-mini',
                        help='LLM model to use (default: o4-mini)')
    
    parser.add_argument('-o', '--output',
                        default='security_results',
                        help='Output directory for results (default: security_results)')
    
    parser.add_argument('-i', '--max-iterations',
                        type=int,
                        default=6,
                        help='Maximum iterations per plan of attack (default: 6)')

    parser.add_argument('-p', '--num-plans',
                        type=int,
                        default=1,
                        help='Number of security testing plans to generate per page. Uses iterative planning: fixed plans are divided into 3 batches (33%% each), unlimited plans (-1) generate 5 plans per batch with adaptive learning. Default: 10')

    parser.add_argument('--disable-baseline-checks', 
                        action='store_true', 
                        help='Disable OWASP Top 10 baseline security checks')
    
    parser.add_argument('--max-plans', 
                        type=int, 
                        default=None,
                        help='Maximum number of plans to generate (default: unlimited)')

    parser.add_argument('--disable-rag',
                        action='store_true',
                        default=True,
                        help='Disable RAG knowledge fetching for faster startup')

    parser.add_argument('--disable-iterative',
                        action='store_true',
                        default=False,
                        help='Disable iterative planning and generate all plans at once (legacy mode)')

    parser.add_argument('--additional-instructions',
                        type=str,
                        default='',
                        help='Additional instructions for the security testing agent')

    # Runtime controls
    parser.add_argument('--browser', choices=['webkit', 'chromium', 'firefox'],
                        default=os.getenv('ROGUE_BROWSER', 'webkit'),
                        help='Browser engine to use (default: webkit)')
    headless_default = os.getenv('ROGUE_HEADLESS', 'true').lower() in ('1','true','yes')
    parser.add_argument('--headless', dest='headless', action='store_true', default=headless_default,
                        help='Run browser headless (default: true)')
    parser.add_argument('--no-headless', dest='headless', action='store_false', help='Run with UI')
    parser.add_argument('--timeout-ms', type=int, default=int(os.getenv('ROGUE_TIMEOUT_MS', '7000')),
                        help='Default timeout (ms) for actions (default: 7000)')
    parser.add_argument('--safe', action='store_true', default=os.getenv('ROGUE_SAFE', 'false').lower() in ('1','true','yes'),
                        help='Enable read-only safe crawl mode (blocks state-changing actions and non-GET XHR/fetch)')
    parser.add_argument('--export-csv', action='store_true', default=False,
                        help='When in --safe mode, also export endpoints.csv and forms.csv')
    parser.add_argument('--include-third-party', action='store_true', default=False,
                        help='Include third-party domains in safe crawl endpoints (default: same-origin only)')

    args = parser.parse_args()

    # Validation
    if not args.url:
        parser.error("URL is required. Use -u or --url to specify the target URL.")
    
    if not args.url.startswith(('http://', 'https://')):
        parser.error("URL must start with http:// or https://")

    print(banner)
    
    print(f"[*] Starting security scan...")
    print(f"[*] Target URL: {args.url}")
    print(f"[*] Using model: {args.model}")
    
    if args.num_plans == -1:
        print(f"[*] Plans per page: Unlimited (15-25+ comprehensive tests with contextual CVE intelligence)")
    elif args.max_plans:
        print(f"[*] Plans per page: {args.max_plans}")
    else:
        print(f"[*] Plans per page: {args.num_plans} (or dynamic based on page complexity)")
    
    print(f"[*] Max iterations per plan: {args.max_iterations}")
    print(f"[*] Results will be saved to: {args.output}")
    if args.safe:
        # Expose CLI toggles to Agent/Reporter via env to minimize signature churn
        os.environ['ROGUE_EXPORT_CSV'] = '1' if args.export_csv else '0'
        os.environ['ROGUE_INCLUDE_THIRD_PARTY'] = '1' if args.include_third_party else '0'
    
    # Check for any supported API key (DeepSeek preferred)
    if not (os.getenv('DEEPSEEK_API_KEY') or os.getenv('OPENAI_API_KEY')):
        print("\n[Error] No API key found. Set DEEPSEEK_API_KEY (recommended) or OPENAI_API_KEY.")
        print("export DEEPSEEK_API_KEY='your-key-here'")
        return
    
    # Create agent with options - combining both parameter sets
    agent = Agent(
        starting_url=args.url,
        expand_scope=args.expand,
        enumerate_subdomains=args.subdomains,
        model=args.model,
        output_dir=args.output,
        max_iterations=args.max_iterations,
        num_plans=args.num_plans,
        enable_baseline_checks=not args.disable_baseline_checks,
        max_plans=args.max_plans,
        disable_rag=args.disable_rag,
        disable_iterative=args.disable_iterative,
        additional_instructions=args.additional_instructions,
        browser=args.browser,
        headless=args.headless,
        timeout_ms=args.timeout_ms,
        safe=args.safe,
    )
    
    # Run the scan
    try:
        agent.run()
        print(f"\n[✅] Scan completed successfully!")
        print(f"[*] Results saved to: {args.output}")
    except KeyboardInterrupt:
        print("\n[*] Scan interrupted by user")
    except Exception as e:
        print(f"\n[❌] Scan failed: {e}")

if __name__ == "__main__":
    main()