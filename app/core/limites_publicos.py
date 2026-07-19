from app.core.rate_limiter import RateLimiter

lecturas = RateLimiter(120, 300)
desafios = RateLimiter(30, 300)
envios = RateLimiter(10, 600)
