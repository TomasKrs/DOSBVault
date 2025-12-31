import csv
import os
import json
import difflib

class OfflineDatabase:
    def __init__(self, csv_path):
        self.csv_path = csv_path
        self.games = []
        self.load_database()

    def load_database(self):
        if not os.path.exists(self.csv_path):
            print(f"Database file not found: {self.csv_path}")
            return

        try:
            with open(self.csv_path, 'r', encoding='utf-8', errors='replace') as f:
                # The file seems to use semicolons. 
                # We'll use csv module with delimiter=';'
                reader = csv.reader(f, delimiter=';')
                header = next(reader, None) # Skip header
                
                for row in reader:
                    if not row or len(row) < 1: continue
                    
                    # Mapping based on: Game Name;Year;Distributor;Developer;Genre;Stars;Players;Description;;;;
                    # Note: The row might have more empty fields at the end.
                    
                    game = {}
                    try:
                        game['name'] = row[0].strip()
                        game['year'] = row[1].strip()
                        game['publisher'] = row[2].strip() # Distributor
                        game['developer'] = row[3].strip()
                        game['genre'] = row[4].strip()
                        
                        # Stars is likely a float or string like "3.4"
                        stars_str = row[5].strip()
                        try:
                            game['rating'] = float(stars_str) if stars_str else 0.0
                        except ValueError:
                            game['rating'] = 0.0
                            
                        game['players'] = row[6].strip()
                        game['description'] = row[7].strip()
                        
                        self.games.append(game)
                    except IndexError:
                        continue
                        
        except Exception as e:
            print(f"Error loading database: {e}")

    def search(self, query):
        if not query: return []
        query_lower = query.lower()
        results = []
        
        # 1. Exact/Substring match
        for game in self.games:
            if query_lower in game['name'].lower():
                results.append(game)
        
        if results:
            return results

        # 2. Fuzzy match
        # Map lower_name -> list of games (in case of duplicates)
        name_map = {}
        for game in self.games:
            n_low = game['name'].lower()
            if n_low not in name_map: name_map[n_low] = []
            name_map[n_low].append(game)
            
        all_names_lower = list(name_map.keys())
        
        matches = difflib.get_close_matches(query_lower, all_names_lower, n=10, cutoff=0.4)
        
        for match in matches:
            results.extend(name_map[match])
                        
        return results

    def get_exact_match(self, name):
        name_lower = name.lower()
        for game in self.games:
            if game['name'].lower() == name_lower:
                return game
        return None
