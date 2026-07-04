import asyncio

from apps.scheduler.tick import SchedulerProcess


def main():
    scheduler = SchedulerProcess()
    asyncio.run(scheduler.start())


if __name__ == "__main__":
    main()
