# πCore Wolfram proxy

A Cloudflare Worker that holds the Wolfram|Alpha AppID so it is never shipped inside the app.
It caches answers for 24 h and rate-limits each IP to 30 requests per minute.

```bash
cd proxy
npx wrangler login
npx wrangler secret put WOLFRAM_APPID     # paste a NEW AppID (rotate the old one)
npx wrangler deploy
```

Then point the app at it, either in `config.json` (`"wolfram_proxy_url": "https://picore-proxy.<you>.workers.dev"`)
or with the `PICORE_WOLFRAM_PROXY` environment variable. When a proxy URL is set, the app sends no AppID.
