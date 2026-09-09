/** Deliver only the newest request, including errors; cancel on unmount. */
export class LatestTask {
  private version = 0;
  cancel() { this.version += 1; }
  async run<T>(task: () => Promise<T>, accept: (value: T) => void, reject: (error: unknown) => void) {
    const version = ++this.version;
    try {
      const value = await task();
      if (version === this.version) accept(value);
    } catch (error) {
      if (version === this.version) reject(error);
    }
  }
}
