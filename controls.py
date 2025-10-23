import time
from pymavlink import mavutil

def send_to_drone(master: mavutil.mavlink_connection, rail: int, pwm: int) -> None:
	master.mav.command_long_send(
	    master.target_system,
	    master.target_component,
	    mavutil.mavlink.MAV_CMD_DO_SET_SERVO,
	    0,
	    rail,
	    pwm,
	    0, 
	    0, 
	    0, 
	    0, 
	    0
	)
	
def main() -> None:
	port = "/dev/ttyAMA0"
	baud = 57600
	
	print(f"Connecting to {port} at {baud} ...")
	master = mavutil.mavlink_connection(port, baud=baud)
	master.wait_heartbeat()
	print(f"Heartbeat OK (sysid={master.target_system})\n")
	
	PIVOT_RAIL = 8
	ACT_RAIL = 7
	
	pivot_val = 1500
	step = 100
	MIN_PWM = 1200
	MAX_PWM = 3000
	
	while True:
		try:
			cmd = input("Enter a (for activate), w/d (to pivot), or q (to quit): ").strip().lower()
		except:
			print("\nExiting ..")
			break
			
		if cmd == "q":
			break
		
		elif cmd in ("w", "d"):
			pivot_val += step if cmd == "w" else -step
			pivot_val = max(MIN_PWM, min(MAX_PWM, pivot_val))
			print(f"Pivot PWM - {pivot_val}")
			send_to_drone(master, PIVOT_RAIL, pivot_val)
			
		elif cmd == "a":
			print("Activated")
			send_to_drone(master, ACT_RAIL, 20000)
			time.sleep(3)
			send_to_drone(master, ACT_RAIL, 0)
			print("Deactivated")
			
		else:
			print("Unrecognized command!")
			
if __name__ == "__main__":
	main()
