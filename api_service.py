import aiohttp
import config

async def get_coin_data(coin_query: str):
    query = coin_query.lower().strip()
    # Пробуем получить данные напрямую
    url = f"https://api.coingecko.com/api/v3/coins/{query}"
    params = {"market_data": "true", "tickers": "false"}
    headers = {"x-cg-demo-api-key": config.CG_API_KEY} if config.CG_API_KEY else {}
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, params=params, headers=headers, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return {
                        "price": data["market_data"]["current_price"]["usd"],
                        "change": data["market_data"]["price_change_percentage_24h"],
                        "ticker": data["symbol"].upper(),
                        "id": data["id"]
                    }
                
                # Если не нашли по ID, ищем через поиск символа
                search_url = f"https://api.coingecko.com/api/v3/search?query={query}"
                async with session.get(search_url, headers=headers) as s_resp:
                    s_data = await s_resp.json()
                    if s_data['coins']:
                        first_coin_id = s_data['coins'][0]['id']
                        return await get_coin_data(first_coin_id) # Рекурсия на 1 уровень
    except Exception as e:
        print(f"API Error: {e}")
    return None

async def get_multi_rsi(coin_id: str):
    # (Код RSI остается таким же, переносим его сюда для порядка)
    intervals = {"1ч": "1", "4ч": "2", "1д": "14"}
    results = []
    headers = {"x-cg-demo-api-key": config.CG_API_KEY} if config.CG_API_KEY else {}
    async with aiohttp.ClientSession() as session:
        for label, days in intervals.items():
            url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
            try:
                async with session.get(url, params={"vs_currency": "usd", "days": days}, headers=headers) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        prices = [p[1] for p in data['prices']][-15:]
                        gains = [prices[i] - prices[i-1] for i in range(1, len(prices)) if prices[i] - prices[i-1] > 0]
                        losses = [abs(prices[i] - prices[i-1]) for i in range(1, len(prices)) if prices[i] - prices[i-1] < 0]
                        avg_g, avg_l = (sum(gains)/14 if gains else 0), (sum(losses)/14 if losses else 1)
                        rsi = 100 - (100 / (1 + (avg_g / (avg_l or 1))))
                        results.append(f"{'🔴' if rsi > 70 else '🟢' if rsi < 30 else '⚪️'} **{label}**: `{rsi:.1f}`")
            except: pass
    return "\n".join(results) or "Нет данных для RSI"
