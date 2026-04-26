import asyncio
import edge_tts

async def main():
    voices = await edge_tts.list_voices()
    vi_voices = [v for v in voices if v["Locale"].startswith("vi")]
    for v in vi_voices:
        print(f"  Name: {v['ShortName']}")
        print(f"  Gender: {v['Gender']}")
        print(f"  Locale: {v['Locale']}")
        print()
    
    if not vi_voices:
        print("No Vietnamese voices found!")
        print("All voices count:", len(voices))
        # Show first 5
        for v in voices[:5]:
            print(f"  {v['ShortName']} ({v['Gender']}, {v['Locale']})")

asyncio.run(main())
