from prosperity.generation.baseline_search import search_baseline_variants

if __name__ == "__main__":
    result = search_baseline_variants()
    print(result["best_variant"])
