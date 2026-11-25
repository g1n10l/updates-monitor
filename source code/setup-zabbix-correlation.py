#!/usr/bin/env python3
"""Install the scoped event correlation required by updates-monitor."""
import argparse
import json
import os
from pathlib import Path
import ssl
import urllib.request


def ensure_correlation(api, definition):
    existing = api('correlation.get', {'output': ['correlationid'],
                                      'filter': {'name': [definition['name']]}})
    if len(existing) > 1:
        raise ValueError('More than one matching correlation rule')
    if existing:
        return api('correlation.update', dict(definition, correlationid=existing[0]['correlationid']))
    return api('correlation.create', definition)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url', required=True, help='Full Zabbix api_jsonrpc.php URL')
    parser.add_argument('--ca-file', help='CA certificate for a private HTTPS endpoint')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()
    definition = json.loads(Path(__file__).with_name('zabbix-updates-monitor-correlation.json').read_text())
    if args.dry_run:
        print(json.dumps(definition, indent=2))
        return
    token = os.environ.get('ZABBIX_API_TOKEN')
    if not token:
        parser.error('Set ZABBIX_API_TOKEN to a Super admin API token')
    context = ssl.create_default_context(cafile=args.ca_file)

    def api(method, params):
        body = json.dumps({'jsonrpc': '2.0', 'method': method, 'params': params, 'id': 1}).encode()
        request = urllib.request.Request(args.url, data=body, headers={
            'Content-Type': 'application/json-rpc', 'Authorization': 'Bearer ' + token})
        with urllib.request.urlopen(request, context=context, timeout=30) as response:
            result = json.load(response)
        if 'error' in result:
            raise RuntimeError(json.dumps(result['error']))
        return result['result']

    print(json.dumps(ensure_correlation(api, definition)))


if __name__ == '__main__':
    main()
