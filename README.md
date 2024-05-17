# XSC003 // Streaming Payments 

- Inspired by protocols like [Superfluid](https://superfluid.finance/) which solve the problem of recurring payments using cryptocurrencies.
- Allows a user to create a stream of payments to a receiver, with a rate and a time window.
- Supports opening a payment stream using a `XSC002 permit`.
- Xian can recommend this feature as the base token standard, enabling subscriptions & recurring payments as standard on all tokens.

## How it works :

The provided methods facilitate the creation and management of payment streams within a smart contract. These streams allow for continuous, time-based payments between parties, defined by a rate and a specific time window. The functionality supports both direct transactions by the sender and transactions authorized through cryptographic permits.

## User Stories : 

#### As a sender I want to be able to:
    - open a stream to a receiver with a rate and a time window
    - close a stream to a receiver, fulfilling outstanding claims to the receiver
    - update a stream to a receiver.
    - open multiple streams to a receiver
    - open multiple streams to multiple receivers
#### As a receiver I want to be able to:
    - claim funds due to me from a sender
    - finalize a stream from a sender
    - forfeit a stream from a sender


### Method: create_stream
`create_stream(receiver: str, rate: float, begins: dict, closes: dict)`

#### Overview
The `create_stream` method facilitates the creation of a new payment stream from the sender to a receiver. This method allows for flexible scheduling of the stream, which can be set to start at any point in the past, present, or future.

#### Functionality
This method performs the following operations to establish a new payment stream:
1. Sender Identification: 
    - The sender of the stream is automatically identified as the caller of the function (ctx.caller).
2. Stream Creation: 
    - The method calls `perform_create_stream`, an internal function that handles the logic for setting up the stream. This includes generating a unique stream ID and validating the parameters such as the start and end times, ensuring the rate is positive, and checking that the stream does not already exist.
3. Return Value: 
    - The unique stream ID is returned, providing a reference to the newly created stream.
This method simplifies the process of initiating a payment stream, making it accessible for users to set up scheduled payments to other parties within the smart contract environment.

### Method : create_stream_from_permit
`create_stream_from_permit(sender: str, receiver: str, rate: float, begins: dict, closes: dict, deadline: str, signature: str)`

#### Overview
The create_stream_from_permit method enables the creation of a payment stream based on a cryptographic permit, which includes a signature that must be verified before the stream can be established. This method allows for secure and verified transactions, ensuring that the stream is initiated based on pre-approved permissions.
#### Functionality
This method performs the following operations to establish a new payment stream using a cryptographic permit:
1. Checks the the deadline has not passed. 
2. Permit Message Construction: 
    - Constructs a permit message using the sender, receiver, rate, and the specified time window (begins and closes). This message is then hashed to create a unique identifier for the permit.
3. Permit Verification:
    - Uniqueness Check: Ensures that the permit has not been used before by checking the hashed permit message against a record of used permits.
4. Signature Verification: 
    - Validates the signature using cryptographic methods to ensure that it was indeed signed by the sender, confirming their intent to create the stream.
5. Permit Registration: 
    - Marks the permit as used in the system to prevent reuse, ensuring the integrity of the permit system.
6. Stream Creation: 
    - Calls perform_create_stream to handle the actual creation of the stream using the validated parameters. This internal function ensures that the stream is set up correctly with all necessary validations.
7. Return Value: 
    - Returns the unique stream ID generated during the stream creation process, providing a reference to the newly established stream.

### Method : balance_stream

`balance_stream(stream_id: str)`

#### Overview

The balance_stream method is designed to facilitate the transfer of funds between a sender and a receiver based on the terms of an active payment stream. This method can be invoked by either the sender or the receiver to calculate and transfer the amount due at the time of the call.


#### Functionality
This method ensures that payment streams are managed fairly and transparently, allowing parties to claim due funds based on the agreed-upon terms of the stream.


1. Existence and Status Check: It first verifies that the stream identified by stream_id exists and is currently active. If the stream does not exist or is not active, the method will raise an assertion error.
2. Time Check: It checks that the current time (now) is after the stream's start time (BEGIN_KEY). This ensures that no funds are transferred before the stream is supposed to begin.
3. Caller Validation: Only the sender or the receiver associated with the stream can call this method to balance the stream. This is enforced by checking if the caller (ctx.caller) is either the sender or the receiver.
4. Calculation of Amount Due: The method calculates the outstanding balance that can be claimed at the time of the call. This is done by determining the amount due from the start of the stream or the last claim, up to the current time or the end of the stream, whichever is earlier.
5. Claimable Amount: It then calculates the actual amount that can be claimed, which is the lesser of the outstanding balance or the sender's current balance. This prevents attempting to claim more than the sender has.
6. Transfer of Funds: The calculated claimable amount is then transferred from the sender's balance to the receiver's balance. This updates the balances of both parties.
7. Update Claimed Amount: The amount claimed is recorded in the stream's data under CLAIMED_KEY to keep track of the total amount that has been transferred over the life of the stream.
7. Return Statement: Finally, the method returns a message indicating the amount of tokens claimed from the stream, providing a clear confirmation of the transaction.


### Method : change_close_time

`change_close_time(stream_id: str, new_close_time: dict)`

#### Overview
The change_close_time method allows the sender of a payment stream to adjust the closing time of an active stream. This functionality is crucial for extending or shortening the duration of a payment stream based on new agreements or circumstances.

#### Functionality

This method performs several operations to ensure the proper management of the stream's lifecycle:
1. Stream Existence and Status Check: 
    - It first checks that the stream identified by `stream_id` exists and is active. If the stream does not exist or is not active, an assertion error is raised.
2. Sender Authorization: 
    - The method ensures that only the sender of the stream can change its closing time. This is enforced by verifying that the caller (`ctx.caller`) is the sender recorded in the stream's data.
3. Adjusting Close Time: 
    - If the new closing time is before the stream's start time and the current time is also before the stream's start time, the closing time is set to the start time. This effectively invalidates the stream by making it non-operational from the start.
    - If the new closing time is in the past or equal to the current time, the stream is closed immediately by setting the closing time to the current time (`now`).
    - Otherwise, the closing time is updated to the new specified time. This allows for the extension or reduction of the stream's duration based on the new closing time.
4. Return Statement: 
    - The method returns a message indicating the new closing time of the stream, providing clear feedback on the operation performed.

### Method : finalize_stream

`finalize_stream(stream_id: str)`

#### Overview
The finalize_stream method is designed to formally close a payment stream between a sender and a receiver. This method ensures that all due balances are settled and that the stream is properly closed without any pending obligations.
#### Functionality

This method performs several critical checks and operations to ensure the stream is correctly finalized:
1. Stream Existence and Status Check: 
    - It verifies that the stream identified by `stream_id` exists and is currently active. If the stream does not exist or is not active, an assertion error is raised.
2. Caller Authorization: 
    - The method ensures that only the sender or the receiver associated with the stream can finalize it. This is enforced by checking if the caller (`ctx.caller`) is either the sender or the receiver.
3. Time Check: 
    - It checks that the current time (`now`) is after or exactly at the stream's closing time (`CLOSE_KEY`). This ensures that the stream is not finalized prematurely.
4. Balance Settlement: 
    - Before finalizing, the method calculates the outstanding balance using `calc_outstanding_balance`, which considers the stream's start time, closing time, rate, and already claimed amount. It asserts that the outstanding balance must be zero, indicating that all due payments have been settled and claimed. This prevents the finalization of streams that still have pending payments.
5. Stream Status Update: 
    - Once all checks are passed, the stream's status is updated to `STREAM_FINALIZED`, indicating that it is officially closed and cannot be reactivated.
6. Return Statement: 
    - The method returns a message confirming the finalization of the stream, providing clear feedback on the operation performed.


### Method : forfeit_stream

`forfeit_stream(stream_id: str)`

#### Overview
The forfeit_stream method allows a receiver to voluntarily forfeit an active payment stream. This action effectively terminates the stream, marking it as forfeited and relinquishing any claims the receiver might have had.
#### Functionality
This method performs several operations to ensure the stream is correctly forfeited:
1. Stream Existence and Status Check: 
    -It first verifies that the stream identified by `stream_id` exists and is currently active. If the stream does not exist or is not active, an assertion error is raised.
2. Receiver Authorization: 
    - The method ensures that only the receiver associated with the stream can forfeit it. This is enforced by checking if the caller (`ctx.caller`) is the receiver recorded in the stream's data.
3. Stream Status Update: 
    - The stream's status is updated to `STREAM_FORFEIT`, indicating that it has been voluntarily terminated by the receiver. Additionally, the closing time of the stream is set to the current time (`now`), marking the exact moment the stream was forfeited.
4. Return Statement: 
    - The method returns a message confirming that the stream has been forfeited, providing clear feedback on the operation performed.

### How to test : 
- Setup testing harness by following the instructions in the [contract dev environment](https://github.com/xian-network/contract-dev-environment)
- Clone this repo to `contracts`
- Run `pytest` in the root directory of the repo
