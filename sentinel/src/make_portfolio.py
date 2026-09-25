"""Seeded generator for a SYNTHETIC demo insurer book (not real Chubb data).
python -m src.make_portfolio  -> data/portfolio.csv, data/travelers.csv"""
import csv, math, pathlib, random

SEED = 20260925
DATA = pathlib.Path("data")
LINES = ["Commercial Property", "High-Net-Worth Homeowners", "Marine Cargo", "Energy",
         "Business Interruption", "Accident & Health", "Travel"]
# name, lat, lon, country, weight, profile (port/energy/resort/metro)
HUBS = [
    ("Houston", 29.76, -95.37, "United States", 5, "energy"), ("New Orleans", 29.95, -90.07, "United States", 3, "port"),
    ("Miami", 25.76, -80.19, "United States", 6, "resort"), ("Tampa", 27.95, -82.46, "United States", 3, "metro"),
    ("Naples FL", 26.14, -81.79, "United States", 2, "resort"), ("Charleston", 32.78, -79.93, "United States", 2, "port"),
    ("New York", 40.71, -74.01, "United States", 7, "metro"), ("Boston", 42.36, -71.06, "United States", 3, "metro"),
    ("Los Angeles", 34.05, -118.24, "United States", 5, "metro"), ("San Francisco", 37.77, -122.42, "United States", 4, "metro"),
    ("San Diego", 32.72, -117.16, "United States", 2, "port"), ("Honolulu", 21.31, -157.86, "United States", 3, "resort"),
    ("Kona / Hilo", 19.64, -155.99, "United States", 2, "resort"), ("Maui", 20.80, -156.33, "United States", 2, "resort"),
    ("Acapulco", 16.85, -99.88, "Mexico", 2, "resort"), ("Cabo San Lucas", 22.89, -109.91, "Mexico", 3, "resort"),
    ("La Paz BCS", 24.14, -110.31, "Mexico", 1, "port"), ("Puerto Vallarta", 20.65, -105.23, "Mexico", 2, "resort"),
    ("Manzanillo", 19.05, -104.32, "Mexico", 2, "port"), ("Mazatlan", 23.25, -106.41, "Mexico", 1, "port"),
    ("Mexico City", 19.43, -99.13, "Mexico", 3, "metro"), ("Cancun", 21.16, -86.85, "Mexico", 2, "resort"),
    ("San Juan", 18.47, -66.11, "Puerto Rico", 2, "resort"), ("Nassau", 25.05, -77.35, "Bahamas", 1, "resort"),
    ("Kingston", 17.97, -76.79, "Jamaica", 1, "port"), ("Santo Domingo", 18.49, -69.93, "Dominican Republic", 1, "metro"),
    ("Tokyo", 35.68, 139.69, "Japan", 5, "metro"), ("Osaka", 34.69, 135.50, "Japan", 3, "port"),
    ("Naha Okinawa", 26.21, 127.68, "Japan", 1, "port"), ("Manila", 14.60, 120.98, "Philippines", 3, "metro"),
    ("Taipei", 25.03, 121.57, "Taiwan", 3, "metro"), ("Kaohsiung", 22.63, 120.30, "Taiwan", 2, "port"),
    ("Shanghai", 31.23, 121.47, "China", 4, "port"), ("Shenzhen", 22.54, 114.06, "China", 3, "port"),
    ("Hong Kong", 22.32, 114.17, "China", 3, "metro"), ("Mumbai", 19.08, 72.88, "India", 3, "metro"),
    ("Chennai", 13.08, 80.27, "India", 2, "port"), ("Visakhapatnam", 17.69, 83.22, "India", 1, "port"),
    ("Kolkata", 22.57, 88.36, "India", 1, "port"), ("Jakarta", -6.21, 106.85, "Indonesia", 3, "metro"),
    ("Surabaya", -7.25, 112.75, "Indonesia", 1, "port"), ("Istanbul", 41.01, 28.98, "Türkiye", 3, "metro"),
    ("Izmir", 38.42, 27.14, "Türkiye", 1, "port"), ("Santiago", -33.45, -70.67, "Chile", 2, "metro"),
    ("Valparaiso", -33.05, -71.62, "Chile", 1, "port"), ("Concepcion", -36.83, -73.05, "Chile", 1, "port"),
    ("Bogota", 4.71, -74.07, "Colombia", 1, "metro"), ("Lima", -12.05, -77.04, "Peru", 1, "metro"),
    ("London", 51.51, -0.13, "United Kingdom", 5, "metro"), ("Rotterdam", 51.92, 4.48, "Netherlands", 2, "port"),
    ("Hamburg", 53.55, 9.99, "Germany", 2, "port"), ("Milan", 45.46, 9.19, "Italy", 2, "metro"),
    ("Valencia", 39.47, -0.38, "Spain", 1, "port"), ("Athens", 37.98, 23.73, "Greece", 1, "metro"),
    ("Lagos", 6.52, 3.38, "Nigeria", 2, "port"), ("Kinshasa", -4.44, 15.27, "Democratic Republic of the Congo", 1, "metro"),
    ("Goma", -1.68, 29.23, "Democratic Republic of the Congo", 1, "metro"), ("Kampala", 0.35, 32.58, "Uganda", 1, "metro"),
    ("Nairobi", -1.29, 36.82, "Kenya", 1, "metro"), ("Johannesburg", -26.20, 28.05, "South Africa", 2, "metro"),
    ("Praia", 14.93, -23.51, "Cape Verde", 1, "resort"), ("Sydney", -33.87, 151.21, "Australia", 2, "metro"),
    ("Dubai", 25.20, 55.27, "United Arab Emirates", 2, "metro"),
]
PROFILE_W = {  # line weights per hub profile
    "energy": [30, 10, 15, 30, 15, 0, 0], "port": [30, 10, 35, 5, 20, 0, 0],
    "resort": [25, 45, 5, 0, 15, 5, 5], "metro": [45, 20, 5, 3, 22, 3, 2],
}
TIV_MED = {"Commercial Property": 25e6, "High-Net-Worth Homeowners": 4e6, "Marine Cargo": 12e6, "Energy": 150e6,
           "Business Interruption": 20e6, "Accident & Health": 2e6, "Travel": 0.5e6}

def main(n=3000):
    rnd = random.Random(SEED); DATA.mkdir(exist_ok=True)
    wsum = sum(h[4] for h in HUBS); rows = []
    for i in range(n):
        h = rnd.choices(HUBS, weights=[x[4] for x in HUBS])[0]
        line = rnd.choices(LINES, weights=PROFILE_W[h[5]])[0]
        d = abs(rnd.gauss(0, 18)); b = rnd.uniform(0, 2 * math.pi)
        lat = h[1] + d / 111 * math.cos(b); lon = h[2] + d / (111 * math.cos(math.radians(h[1]))) * math.sin(b)
        tiv = round(TIV_MED[line] * math.exp(rnd.gauss(0, 0.8)), -3)
        rows.append({"id": f"LOC{i:05d}", "name": f"{h[0]} {line.split()[0]} #{i:04d}", "lat": round(lat, 4),
                     "lon": round(lon, 4), "country": h[3], "line": line, "tiv_usd": int(tiv), "hub": h[0]})
    with (DATA / "portfolio.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
    countries = sorted({h[3] for h in HUBS} | {"Rwanda", "Burundi", "South Sudan", "Tanzania", "Angola"})
    with (DATA / "travelers.csv").open("w", newline="") as f:
        w = csv.writer(f); w.writerow(["country", "insured_travelers", "ah_members"])
        for c in countries:
            wt = sum(h[4] for h in HUBS if h[3] == c) or 0.5
            w.writerow([c, int(wt * rnd.randint(300, 900)), int(wt * rnd.randint(800, 2500))])
    print(f"SYNTHETIC demo book: {len(rows)} locations, TIV ${sum(r['tiv_usd'] for r in rows)/1e9:.1f}B -> data/portfolio.csv")

if __name__ == "__main__":
    main()
