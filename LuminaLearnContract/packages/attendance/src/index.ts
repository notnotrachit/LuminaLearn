import { Buffer } from "buffer";
import { Address } from '@stellar/stellar-sdk';
import {
  AssembledTransaction,
  Client as ContractClient,
  ClientOptions as ContractClientOptions,
  MethodOptions,
  Result,
  Spec as ContractSpec,
} from '@stellar/stellar-sdk/contract';
import type {
  u32,
  i32,
  u64,
  i64,
  u128,
  i128,
  u256,
  i256,
  Option,
  Typepoint,
  Duration,
} from '@stellar/stellar-sdk/contract';
export * from '@stellar/stellar-sdk'
export * as contract from '@stellar/stellar-sdk/contract'
export * as rpc from '@stellar/stellar-sdk/rpc'

if (typeof window !== 'undefined') {
  //@ts-ignore Buffer exists
  window.Buffer = window.Buffer || Buffer;
}


export const networks = {
  testnet: {
    networkPassphrase: "Test SDF Network ; September 2015",
    contractId: "CA3BC5TPJXTKCQ7IWYPIZCHAL3A6FY7XOC77IGRM7ODGKDTYO4I423Z5",
  }
} as const

export const Errors = {
  1: {message:"NotInitialized"},

  2: {message:"AlreadyInitialized"},

  3: {message:"Unauthorized"},

  4: {message:"LectureNotFound"},

  5: {message:"SessionNotActive"},

  6: {message:"SessionExpired"},

  7: {message:"InvalidNonce"},

  8: {message:"AlreadyMarked"},

  9: {message:"AttendancePeriodNotStarted"},

  10: {message:"StudentAlreadyEnrolled"}
}

export interface Student {
  address: string;
  name: string;
  roll_no: u64;
}


export interface Client {
  /**
   * Construct and simulate a initialize transaction. Returns an `AssembledTransaction` object which will have a `result` field containing the result of the simulation. If this transaction changes contract state, you will need to call `signAndSend()` on the returned object.
   * Initialize the contract, setting the teacher/admin.
   * Can only be called once.
   */
  initialize: ({teacher}: {teacher: string}, options?: {
    /**
     * The fee to pay for the transaction. Default: BASE_FEE
     */
    fee?: number;

    /**
     * The maximum amount of time to wait for the transaction to complete. Default: DEFAULT_TIMEOUT
     */
    timeoutInSeconds?: number;

    /**
     * Whether to automatically simulate the transaction when constructing the AssembledTransaction. Default: true
     */
    simulate?: boolean;
  }) => Promise<AssembledTransaction<Result<void>>>

  /**
   * Construct and simulate a create_lecture transaction. Returns an `AssembledTransaction` object which will have a `result` field containing the result of the simulation. If this transaction changes contract state, you will need to call `signAndSend()` on the returned object.
   * Allows the teacher to create a new lecture entry.
   */
  create_lecture: ({teacher, lecture_id}: {teacher: string, lecture_id: u64}, options?: {
    /**
     * The fee to pay for the transaction. Default: BASE_FEE
     */
    fee?: number;

    /**
     * The maximum amount of time to wait for the transaction to complete. Default: DEFAULT_TIMEOUT
     */
    timeoutInSeconds?: number;

    /**
     * Whether to automatically simulate the transaction when constructing the AssembledTransaction. Default: true
     */
    simulate?: boolean;
  }) => Promise<AssembledTransaction<Result<void>>>

  /**
   * Construct and simulate a add_student transaction. Returns an `AssembledTransaction` object which will have a `result` field containing the result of the simulation. If this transaction changes contract state, you will need to call `signAndSend()` on the returned object.
   * Allows the teacher to add/enroll a student to a specific lecture.
   */
  add_student: ({teacher, lecture_id, roll_no, name, student_address}: {teacher: string, lecture_id: u64, roll_no: u64, name: string, student_address: string}, options?: {
    /**
     * The fee to pay for the transaction. Default: BASE_FEE
     */
    fee?: number;

    /**
     * The maximum amount of time to wait for the transaction to complete. Default: DEFAULT_TIMEOUT
     */
    timeoutInSeconds?: number;

    /**
     * Whether to automatically simulate the transaction when constructing the AssembledTransaction. Default: true
     */
    simulate?: boolean;
  }) => Promise<AssembledTransaction<Result<void>>>

  /**
   * Construct and simulate a start_attendance transaction. Returns an `AssembledTransaction` object which will have a `result` field containing the result of the simulation. If this transaction changes contract state, you will need to call `signAndSend()` on the returned object.
   * Starts an attendance session for a given lecture.
   * Generates a random nonce and sets an expiry time (e.g., 5 minutes).
   * Returns the nonce to be used off-chain (e.g., in a QR code).
   */
  start_attendance: ({teacher, lecture_id, duration_seconds}: {teacher: string, lecture_id: u64, duration_seconds: u64}, options?: {
    /**
     * The fee to pay for the transaction. Default: BASE_FEE
     */
    fee?: number;

    /**
     * The maximum amount of time to wait for the transaction to complete. Default: DEFAULT_TIMEOUT
     */
    timeoutInSeconds?: number;

    /**
     * Whether to automatically simulate the transaction when constructing the AssembledTransaction. Default: true
     */
    simulate?: boolean;
  }) => Promise<AssembledTransaction<Result<Buffer>>>

  /**
   * Construct and simulate a mark_attendance transaction. Returns an `AssembledTransaction` object which will have a `result` field containing the result of the simulation. If this transaction changes contract state, you will need to call `signAndSend()` on the returned object.
   * Allows a student to mark their attendance using the nonce provided off-chain.
   */
  mark_attendance: ({student, lecture_id, nonce}: {student: string, lecture_id: u64, nonce: Buffer}, options?: {
    /**
     * The fee to pay for the transaction. Default: BASE_FEE
     */
    fee?: number;

    /**
     * The maximum amount of time to wait for the transaction to complete. Default: DEFAULT_TIMEOUT
     */
    timeoutInSeconds?: number;

    /**
     * Whether to automatically simulate the transaction when constructing the AssembledTransaction. Default: true
     */
    simulate?: boolean;
  }) => Promise<AssembledTransaction<Result<void>>>

  /**
   * Construct and simulate a get_attendance transaction. Returns an `AssembledTransaction` object which will have a `result` field containing the result of the simulation. If this transaction changes contract state, you will need to call `signAndSend()` on the returned object.
   * Check if a student is marked present for a specific lecture.
   */
  get_attendance: ({lecture_id, student}: {lecture_id: u64, student: string}, options?: {
    /**
     * The fee to pay for the transaction. Default: BASE_FEE
     */
    fee?: number;

    /**
     * The maximum amount of time to wait for the transaction to complete. Default: DEFAULT_TIMEOUT
     */
    timeoutInSeconds?: number;

    /**
     * Whether to automatically simulate the transaction when constructing the AssembledTransaction. Default: true
     */
    simulate?: boolean;
  }) => Promise<AssembledTransaction<boolean>>

  /**
   * Construct and simulate a get_student_enrollment transaction. Returns an `AssembledTransaction` object which will have a `result` field containing the result of the simulation. If this transaction changes contract state, you will need to call `signAndSend()` on the returned object.
   * Get the enrollment details for a specific student in a lecture.
   */
  get_student_enrollment: ({lecture_id, student_address}: {lecture_id: u64, student_address: string}, options?: {
    /**
     * The fee to pay for the transaction. Default: BASE_FEE
     */
    fee?: number;

    /**
     * The maximum amount of time to wait for the transaction to complete. Default: DEFAULT_TIMEOUT
     */
    timeoutInSeconds?: number;

    /**
     * Whether to automatically simulate the transaction when constructing the AssembledTransaction. Default: true
     */
    simulate?: boolean;
  }) => Promise<AssembledTransaction<Option<Student>>>

  /**
   * Construct and simulate a get_teacher transaction. Returns an `AssembledTransaction` object which will have a `result` field containing the result of the simulation. If this transaction changes contract state, you will need to call `signAndSend()` on the returned object.
   * Get the teacher address.
   */
  get_teacher: (options?: {
    /**
     * The fee to pay for the transaction. Default: BASE_FEE
     */
    fee?: number;

    /**
     * The maximum amount of time to wait for the transaction to complete. Default: DEFAULT_TIMEOUT
     */
    timeoutInSeconds?: number;

    /**
     * Whether to automatically simulate the transaction when constructing the AssembledTransaction. Default: true
     */
    simulate?: boolean;
  }) => Promise<AssembledTransaction<Result<string>>>

}
export class Client extends ContractClient {
  static async deploy<T = Client>(
    /** Options for initalizing a Client as well as for calling a method, with extras specific to deploying. */
    options: MethodOptions &
      Omit<ContractClientOptions, "contractId"> & {
        /** The hash of the Wasm blob, which must already be installed on-chain. */
        wasmHash: Buffer | string;
        /** Salt used to generate the contract's ID. Passed through to {@link Operation.createCustomContract}. Default: random. */
        salt?: Buffer | Uint8Array;
        /** The format used to decode `wasmHash`, if it's provided as a string. */
        format?: "hex" | "base64";
      }
  ): Promise<AssembledTransaction<T>> {
    return ContractClient.deploy(null, options)
  }
  constructor(public readonly options: ContractClientOptions) {
    super(
      new ContractSpec([ "AAAABAAAAAAAAAAAAAAABUVycm9yAAAAAAAACgAAAAAAAAAOTm90SW5pdGlhbGl6ZWQAAAAAAAEAAAAAAAAAEkFscmVhZHlJbml0aWFsaXplZAAAAAAAAgAAAAAAAAAMVW5hdXRob3JpemVkAAAAAwAAAAAAAAAPTGVjdHVyZU5vdEZvdW5kAAAAAAQAAAAAAAAAEFNlc3Npb25Ob3RBY3RpdmUAAAAFAAAAAAAAAA5TZXNzaW9uRXhwaXJlZAAAAAAABgAAAAAAAAAMSW52YWxpZE5vbmNlAAAABwAAAAAAAAANQWxyZWFkeU1hcmtlZAAAAAAAAAgAAAAAAAAAGkF0dGVuZGFuY2VQZXJpb2ROb3RTdGFydGVkAAAAAAAJAAAAAAAAABZTdHVkZW50QWxyZWFkeUVucm9sbGVkAAAAAAAK",
        "AAAAAQAAAAAAAAAAAAAAB1N0dWRlbnQAAAAAAwAAAAAAAAAHYWRkcmVzcwAAAAATAAAAAAAAAARuYW1lAAAAEAAAAAAAAAAHcm9sbF9ubwAAAAAG",
        "AAAAAAAAAExJbml0aWFsaXplIHRoZSBjb250cmFjdCwgc2V0dGluZyB0aGUgdGVhY2hlci9hZG1pbi4KQ2FuIG9ubHkgYmUgY2FsbGVkIG9uY2UuAAAACmluaXRpYWxpemUAAAAAAAEAAAAAAAAAB3RlYWNoZXIAAAAAEwAAAAEAAAPpAAAD7QAAAAAAAAAD",
        "AAAAAAAAADFBbGxvd3MgdGhlIHRlYWNoZXIgdG8gY3JlYXRlIGEgbmV3IGxlY3R1cmUgZW50cnkuAAAAAAAADmNyZWF0ZV9sZWN0dXJlAAAAAAACAAAAAAAAAAd0ZWFjaGVyAAAAABMAAAAAAAAACmxlY3R1cmVfaWQAAAAAAAYAAAABAAAD6QAAA+0AAAAAAAAAAw==",
        "AAAAAAAAAEFBbGxvd3MgdGhlIHRlYWNoZXIgdG8gYWRkL2Vucm9sbCBhIHN0dWRlbnQgdG8gYSBzcGVjaWZpYyBsZWN0dXJlLgAAAAAAAAthZGRfc3R1ZGVudAAAAAAFAAAAAAAAAAd0ZWFjaGVyAAAAABMAAAAAAAAACmxlY3R1cmVfaWQAAAAAAAYAAAAAAAAAB3JvbGxfbm8AAAAABgAAAAAAAAAEbmFtZQAAABAAAAAAAAAAD3N0dWRlbnRfYWRkcmVzcwAAAAATAAAAAQAAA+kAAAPtAAAAAAAAAAM=",
        "AAAAAAAAALJTdGFydHMgYW4gYXR0ZW5kYW5jZSBzZXNzaW9uIGZvciBhIGdpdmVuIGxlY3R1cmUuCkdlbmVyYXRlcyBhIHJhbmRvbSBub25jZSBhbmQgc2V0cyBhbiBleHBpcnkgdGltZSAoZS5nLiwgNSBtaW51dGVzKS4KUmV0dXJucyB0aGUgbm9uY2UgdG8gYmUgdXNlZCBvZmYtY2hhaW4gKGUuZy4sIGluIGEgUVIgY29kZSkuAAAAAAAQc3RhcnRfYXR0ZW5kYW5jZQAAAAMAAAAAAAAAB3RlYWNoZXIAAAAAEwAAAAAAAAAKbGVjdHVyZV9pZAAAAAAABgAAAAAAAAAQZHVyYXRpb25fc2Vjb25kcwAAAAYAAAABAAAD6QAAA+4AAAAgAAAAAw==",
        "AAAAAAAAAE1BbGxvd3MgYSBzdHVkZW50IHRvIG1hcmsgdGhlaXIgYXR0ZW5kYW5jZSB1c2luZyB0aGUgbm9uY2UgcHJvdmlkZWQgb2ZmLWNoYWluLgAAAAAAAA9tYXJrX2F0dGVuZGFuY2UAAAAAAwAAAAAAAAAHc3R1ZGVudAAAAAATAAAAAAAAAApsZWN0dXJlX2lkAAAAAAAGAAAAAAAAAAVub25jZQAAAAAAA+4AAAAgAAAAAQAAA+kAAAPtAAAAAAAAAAM=",
        "AAAAAAAAADxDaGVjayBpZiBhIHN0dWRlbnQgaXMgbWFya2VkIHByZXNlbnQgZm9yIGEgc3BlY2lmaWMgbGVjdHVyZS4AAAAOZ2V0X2F0dGVuZGFuY2UAAAAAAAIAAAAAAAAACmxlY3R1cmVfaWQAAAAAAAYAAAAAAAAAB3N0dWRlbnQAAAAAEwAAAAEAAAAB",
        "AAAAAAAAAD9HZXQgdGhlIGVucm9sbG1lbnQgZGV0YWlscyBmb3IgYSBzcGVjaWZpYyBzdHVkZW50IGluIGEgbGVjdHVyZS4AAAAAFmdldF9zdHVkZW50X2Vucm9sbG1lbnQAAAAAAAIAAAAAAAAACmxlY3R1cmVfaWQAAAAAAAYAAAAAAAAAD3N0dWRlbnRfYWRkcmVzcwAAAAATAAAAAQAAA+gAAAfQAAAAB1N0dWRlbnQA",
        "AAAAAAAAABhHZXQgdGhlIHRlYWNoZXIgYWRkcmVzcy4AAAALZ2V0X3RlYWNoZXIAAAAAAAAAAAEAAAPpAAAAEwAAAAM=" ]),
      options
    )
  }
  public readonly fromJSON = {
    initialize: this.txFromJSON<Result<void>>,
        create_lecture: this.txFromJSON<Result<void>>,
        add_student: this.txFromJSON<Result<void>>,
        start_attendance: this.txFromJSON<Result<Buffer>>,
        mark_attendance: this.txFromJSON<Result<void>>,
        get_attendance: this.txFromJSON<boolean>,
        get_student_enrollment: this.txFromJSON<Option<Student>>,
        get_teacher: this.txFromJSON<Result<string>>
  }
}