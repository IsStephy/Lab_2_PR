import requests
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
import statistics
import socket

def get_my_ip():
    """Get the local IP address of this machine."""
    try:
        # Create a socket to determine local IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        local_ip = s.getsockname()[0]
        s.close()
        return local_ip
    except:
        return "localhost"

def make_request(url, request_id):
    """Make a single HTTP request and return timing info."""
    start = time.time()
    try:
        response = requests.get(url, timeout=10)
        end = time.time()
        return {
            'id': request_id,
            'status': response.status_code,
            'duration': end - start,
            'success': response.status_code == 200
        }
    except Exception as e:
        end = time.time()
        return {
            'id': request_id,
            'status': 'error',
            'duration': end - start,
            'success': False,
            'error': str(e)
        }

def test_concurrent_requests(url, num_requests=10):
    """Test server with concurrent requests."""
    print(f"\n{'='*60}")
    print(f"Testing with {num_requests} concurrent requests")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    results = []
    
    # Make concurrent requests
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [
            executor.submit(make_request, url, i) 
            for i in range(num_requests)
        ]
        
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            status = "✓" if result['success'] else "✗"
            print(f"{status} Request {result['id']}: "
                  f"Status={result['status']}, "
                  f"Duration={result['duration']:.3f}s")
    
    end_time = time.time()
    total_time = end_time - start_time
    
    # Calculate statistics
    successful = [r for r in results if r['success']]
    durations = [r['duration'] for r in successful]
    
    print(f"\n{'='*60}")
    print("RESULTS:")
    print(f"{'='*60}")
    print(f"Total time: {total_time:.3f}s")
    print(f"Successful requests: {len(successful)}/{num_requests}")
    
    if durations:
        print(f"Average request duration: {statistics.mean(durations):.3f}s")
        print(f"Min request duration: {min(durations):.3f}s")
        print(f"Max request duration: {max(durations):.3f}s")
        print(f"Throughput: {len(successful)/total_time:.2f} requests/second")
    
    return total_time, len(successful)

def test_race_condition(url, num_requests=50):
    """Test counter race condition by making many concurrent requests to the same file."""
    print(f"\n{'='*60}")
    print(f"Testing RACE CONDITION with {num_requests} concurrent requests")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    with ThreadPoolExecutor(max_workers=num_requests) as executor:
        futures = [executor.submit(make_request, url, i) for i in range(num_requests)]
        results = [f.result() for f in as_completed(futures)]
    
    successful = len([r for r in results if r['success']])
    print(f"\nCompleted {successful} successful requests")
    print(f"Check the directory listing to see if counter shows {successful}")
    print(f"If it shows less, there's a race condition!")

def test_rate_limiting(url, requests_per_second, duration_seconds=10):
    """Test rate limiting by sending requests at a controlled rate."""
    print(f"\n{'='*60}")
    print(f"Testing RATE LIMITING: {requests_per_second} requests/second for {duration_seconds}s")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    delay = 1.0 / requests_per_second
    start_time = time.time()
    results = []
    request_count = 0
    
    while time.time() - start_time < duration_seconds:
        result = make_request(url, request_count)
        results.append(result)
        
        status_symbol = "✓" if result['success'] else "✗"
        if result['status'] == 429:
            print(f"{status_symbol} Request {request_count}: RATE LIMITED (429)")
        else:
            print(f"{status_symbol} Request {request_count}: {result['status']}")
        
        request_count += 1
        time.sleep(delay)
    
    total_time = time.time() - start_time
    successful = [r for r in results if r['success']]
    rate_limited = [r for r in results if r['status'] == 429]
    
    print(f"\n{'='*60}")
    print("RATE LIMITING RESULTS:")
    print(f"{'='*60}")
    print(f"Total requests: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Rate limited (429): {len(rate_limited)}")
    print(f"Actual rate: {len(results)/total_time:.2f} requests/second")
    print(f"Success rate: {len(successful)/total_time:.2f} requests/second")

def spam_requests(url, duration_seconds=5):
    """Spam server with requests as fast as possible."""
    print(f"\n{'='*60}")
    print(f"SPAMMING server for {duration_seconds} seconds")
    print(f"URL: {url}")
    print(f"{'='*60}\n")
    
    start_time = time.time()
    results = []
    request_count = 0
    
    while time.time() - start_time < duration_seconds:
        result = make_request(url, request_count)
        results.append(result)
        request_count += 1
        
        # Print every 10th request
        if request_count % 10 == 0:
            rate_limited = len([r for r in results if r['status'] == 429])
            print(f"Sent {request_count} requests, {rate_limited} rate-limited so far...")
    
    total_time = time.time() - start_time
    successful = [r for r in results if r['success']]
    rate_limited = [r for r in results if r['status'] == 429]
    
    print(f"\n{'='*60}")
    print("SPAM RESULTS:")
    print(f"{'='*60}")
    print(f"Total requests: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Rate limited (429): {len(rate_limited)}")
    print(f"Request rate: {len(results)/total_time:.2f} requests/second")
    print(f"Success throughput: {len(successful)/total_time:.2f} requests/second")
    print(f"Rate limit effectiveness: {len(rate_limited)/len(results)*100:.1f}% blocked")

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(
        description='Test HTTP server performance',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Test local server
  python test_concurrent.py --host localhost --port 8080 --test concurrent
  
  # Test friend's server (they give you their IP)
  python test_concurrent.py --host 192.168.1.100 --port 8080 --test spam
  
  # Full URL (alternative)
  python test_concurrent.py --url http://192.168.1.6:8080/test.html --test race
  
  # Get your IP to share with friends
  python test_concurrent.py --show-ip
        """
    )
    
    parser.add_argument('--host', default=None, 
                        help='Server IP address (e.g., 192.168.1.100 or your.friend.ip.address)')
    parser.add_argument('--port', type=int, default=8080,
                        help='Server port (default: 8080)')
    parser.add_argument('--url', default=None, 
                        help='Full URL to test (overrides --host and --port)')
    parser.add_argument('--test', choices=['concurrent', 'race', 'ratelimit', 'spam', 'all'],
                        default='concurrent', help='Type of test to run')
    parser.add_argument('--requests', type=int, default=10,
                        help='Number of concurrent requests (default: 10)')
    parser.add_argument('--rate', type=float, default=4.5,
                        help='Requests per second for rate limit test (default: 4.5)')
    parser.add_argument('--duration', type=int, default=10,
                        help='Duration in seconds for rate limit test (default: 10)')
    parser.add_argument('--show-ip', action='store_true',
                        help='Show your local IP address and exit')
    
    args = parser.parse_args()
    
    # Show IP and exit
    if args.show_ip:
        my_ip = get_my_ip()
        print(f"\n{'='*60}")
        print("YOUR IP ADDRESS INFORMATION")
        print(f"{'='*60}")
        print(f"Your local IP: {my_ip}")
        print(f"\nShare this with your friends so they can test your server:")
        print(f"  python test_concurrent.py --host {my_ip} --port 8080 --test spam")
        print(f"\nOr use the full URL:")
        print(f"  python test_concurrent.py --url http://{my_ip}:8080/test.html --test race")
        print(f"\n{'='*60}")
        exit(0)
    
    # Build URL
    if args.url:
        url = args.url
        # Extract host for display
        from urllib.parse import urlparse
        parsed = urlparse(url)
        display_host = parsed.hostname or "unknown"
    elif args.host:
        url = f"http://{args.host}:{args.port}/"
        display_host = args.host
    else:
        # Default to localhost
        url = f"http://localhost:{args.port}/"
        display_host = "localhost"
    
    # Display connection info
    my_ip = get_my_ip()
    print(f"\n{'='*60}")
    print("CONNECTION INFO")
    print(f"{'='*60}")
    print(f"Your IP: {my_ip}")
    print(f"Testing server at: {display_host}")
    print(f"Target URL: {url}")
    
    if display_host == "localhost" or display_host == "127.0.0.1":
        print(f"\n⚠️  Testing LOCAL server")
        print(f"   To test a friend's server, use:")
        print(f"   python test_concurrent.py --host <friend-ip> --port {args.port}")
    else:
        print(f"\n✓ Testing REMOTE server at {display_host}")
    
    print(f"{'='*60}\n")
    
    # Run tests
    if args.test == 'concurrent' or args.test == 'all':
        test_concurrent_requests(url, args.requests)
    
    if args.test == 'race' or args.test == 'all':
        print("\n\nNow testing for race conditions...")
        test_race_condition(url, 50)
    
    if args.test == 'ratelimit' or args.test == 'all':
        print("\n\nNow testing rate limiting (below limit)...")
        test_rate_limiting(url, args.rate, args.duration)
    
    if args.test == 'spam' or args.test == 'all':
        print("\n\nNow testing with spam (exceeding rate limit)...")
        spam_requests(url, 5)
    
    print("\n" + "="*60)
    print("Testing complete!")
    print("="*60)