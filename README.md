# care_ai_search

AI-powered search plugin for [OHC Care](https://github.com/ohcnetwork/care). Scaffolded following the [ohcnetwork/care-plugin-cookiecutter](https://github.com/ohcnetwork/care-plugin-cookiecutter) layout (mirrors `care_abdm`).

## Installation

Add to `care/plug_config.py`:

```python
care_ai_search_plug = Plug(
    name="care_ai_search",
    package_name="git+https://github.com/<you>/care_ai_search.git",
    version="@main",
    configs={},
)
plugs = [care_ai_search_plug]
```

### Local development

```bash
# from the care repo root
pip install -e ../care_ai_search
python manage.py makemigrations care_ai_search
python manage.py migrate
```

## License

MIT.
