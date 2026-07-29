# Land Forum

Public website for Land Forum and the Detroit Board of Zoning Appeals atlas.

## Develop

```bash
python scripts/build_bza_data.py
npm install
npm run dev
```

The public atlas data is generated from the repository’s normalized BZA case
histories and matched assessor parcels. Do not edit `public/data/bza-cases.json`
by hand.
