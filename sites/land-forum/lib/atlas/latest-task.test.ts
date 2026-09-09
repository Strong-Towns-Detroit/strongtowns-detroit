import test from "node:test";
import assert from "node:assert/strict";
import { LatestTask } from "./latest-task.ts";

const unexpected = (value: unknown) => assert.fail(String(value));

function deferred<T>() {
  let resolve!: (value: T) => void;
  let reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}

test("a slow earlier parcel response cannot overwrite the latest selection", async () => {
  const latest = new LatestTask();
  const first = deferred<string>(), second = deferred<string>();
  const selected: string[] = [];
  const one = latest.run(() => first.promise, (id) => selected.push(id), unexpected);
  const two = latest.run(() => second.promise, (id) => selected.push(id), unexpected);
  second.resolve("new parcel");
  await two;
  first.resolve("old parcel");
  await one;
  assert.deepEqual(selected, ["new parcel"]);
});

test("obsolete failures and responses after unmount do not update the inspector", async () => {
  const latest = new LatestTask();
  const first = deferred<string>();
  const one = latest.run(() => first.promise, unexpected, unexpected);
  latest.cancel();
  first.reject(new Error("obsolete failure"));
  await one;
  const second = deferred<string>();
  const two = latest.run(() => second.promise, unexpected, unexpected);
  latest.cancel();
  second.resolve("unmounted");
  await two;
});

test("a current failure is surfaced and a retry can succeed", async () => {
  const latest = new LatestTask();
  const errors: unknown[] = [], selected: string[] = [];
  await latest.run(async () => { throw new Error("network failed"); }, unexpected, (error) => errors.push(error));
  await latest.run(async () => "retried parcel", (id) => selected.push(id), unexpected);
  assert.equal(errors.length, 1);
  assert.deepEqual(selected, ["retried parcel"]);
});
