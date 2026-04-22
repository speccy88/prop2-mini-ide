from pathlib import Path
p=Path('blink_test.binary')
data=p.read_bytes()
hex_pairs = ' '.join(f"{b:02x}" for b in data)
cmd=f"Prop_Hex 0 0 0 0 {hex_pairs} ~"
print(cmd[:200])
print('...')
print('Length bytes:', len(data))
