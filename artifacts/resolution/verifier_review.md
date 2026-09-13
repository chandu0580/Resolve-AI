# Verifier review sheet (DEV drafts)

## 554777:A_v1  [passed]  intent=keyboard_text_bug level=STRONG
- customer: Oye iPhones this annoying “I️” question mark bug is gettin out of hand. It’s making all my texts unintelligible...enough already!
- draft: We hear you, and we know this has been frustrating. An update has been released to fix this autocorrect issue. Please back up your device, then update to iOS 11.1.1. Let us know if the issue persists afterwards.
- refs: ['2205900', '2311614', '2367740', '2547216']  issues: []
  - cited [update] An update has been released to assist with this issue. If you haven’t yet, please back up your device and update it to the latest version iOS 11.1.1. For more info, check out: <url>
  - cited [update] iOS 11.1.1 was recently released and it includes a fix for autocorrect issues. Be sure to back up your device prior to updating, and let us know if the issue persists afterwards. How to back up: <url>
  - cited [update] To help resolve this issue we recommend backing up, then updating to iOS 11.1.1. You can learn more about this issue, and how to update, here: <url>
  - cited [update] We recently released an iOS update, 11.1.1, that contains a fix for autocorrect issues. Let’s be sure to back up your device prior to updating. How to back up: <url>

## 554777:B_v2  [passed]  intent=keyboard_text_bug level=STRONG
- customer: Oye iPhones this annoying “I️” question mark bug is gettin out of hand. It’s making all my texts unintelligible...enough already!
- draft: iOS 11.1.1 was recently released and it includes a fix for autocorrect issues. Be sure to back up your device prior to updating, and let us know if the issue persists afterwards. You can find the steps on our support site.
- refs: ['2311614']  issues: []
  - cited [update] iOS 11.1.1 was recently released and it includes a fix for autocorrect issues. Be sure to back up your device prior to updating, and let us know if the issue persists afterwards. How to back up: <url>

## 2873402:A_v1  [passed]  intent=keyboard_text_bug level=STRONG
- customer: Can you fix all these issues with the letter “eye”. Now this “I.T” is happening when you type the word “it”. Fix your shit
- draft: We understand the frustration with the keyboard autocorrect issue. There's a workaround you can try until this is fixed in a future software update. Let us know if you'd like more details on the steps.
- refs: ['1708534']  issues: []
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>

## 2873402:B_v2  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: Can you fix all these issues with the letter “eye”. Now this “I.T” is happening when you type the word “it”. Fix your shit
- draft: We're sorry for the frustration with your keyboard! Here's what you can do to work around the issue until it's fixed in a future software update: check out the steps on our support site. We appreciate your patience while we get this sorted.
- refs: ['1708534']  issues: ['llm_support_check:verifier unavailable: structured output invalid after retry: no JSON object in response']
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>

## 553457:A_v1  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: Now the iPhone trying to turn “it” into “I.T” #glitches
- draft: Thanks for reaching out about this autocorrect issue. Let's work together to get this sorted. To start, what device model and software version are you using?
- refs: ['2798396']  issues: ['llm_support_check:The issue is an autocorrect issue']
  - cited [ask_info] Thank you for reaching out to us. Let’s work together to find the best course of action for this issue. To start, what device model and software version are you using?

## 553457:B_v2  [passed]  intent=keyboard_text_bug level=STRONG
- customer: Now the iPhone trying to turn “it” into “I.T” #glitches
- draft: Here's what you can do to work around the issue until it's fixed in a future software update: the steps on our support site.
- refs: ['2169762']  issues: []
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>

## 487914:A_v1  [passed]  intent=keyboard_text_bug level=STRONG
- customer: why hasn’t the I️ ? Issue been fixed yet?
- draft: We've recently released an update that addresses this issue. We recommend creating a current backup of your device before updating. Let us know if this helps!
- refs: ['2573954', '2343731']  issues: []
  - cited [update] We've recently released an update to fix this. We do recommend creating a current backup of the data on your device before updating. Here's more about the new update: <url> Let us know if this helps. <url>
  - cited [update] Hi there. We’ve recently released an update which addresses this issue. Don’t forget to create a backup of your device before you update: <url>

## 487914:B_v2  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: why hasn’t the I️ ? Issue been fixed yet?
- draft: We've recently released an update to fix this. We recommend creating a current backup of your device before updating. You can find the steps on our support site. Let us know if this helps!
- refs: ['2573954']  issues: ['llm_support_check:You can find the steps on our support site.']
  - cited [update] We've recently released an update to fix this. We do recommend creating a current backup of the data on your device before updating. Here's more about the new update: <url> Let us know if this helps. <url>

## 2871669:A_v1  [passed]  intent=performance_crash level=STRONG
- customer: Care to fix the “I️” glitch anytime soon?
- draft: We're here to help. We've released an update created to address this issue. Back up your iPhone and update to get this resolved.
- refs: ['2293080']  issues: []
  - cited [update] We're here to help. We released an update created to address this issue. Backup your iPhone and update following these steps: <url>

## 2871669:B_v2  [passed]  intent=performance_crash level=STRONG
- customer: Care to fix the “I️” glitch anytime soon?
- draft: We're here to help. We released an update created to address this issue. Backup your iPhone and update following the steps on our support site.
- refs: ['2293080']  issues: []
  - cited [update] We're here to help. We released an update created to address this issue. Backup your iPhone and update following these steps: <url>

## 101285:A_v1  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: Anybody else getting really annoyed with trying to type “it” and constantly having it autocorrect to I.T ???? What’s good with that ???
- draft: We understand how frustrating autocorrect can be! Could you let us know which iOS version and device you're using? This will help us look into what's happening with that autocorrect behavior.
- refs: []  issues: ['evidence_refs:no valid evidence references']

## 101285:B_v2  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: Anybody else getting really annoyed with trying to type “it” and constantly having it autocorrect to I.T ???? What’s good with that ???
- draft: We've recently released an update to fix autocorrect issues like this. We recommend creating a current backup of your device before updating. You can find the steps on our support site. Let us know if this helps!
- refs: ['2573954']  issues: ['llm_support_check:verifier unavailable: structured output invalid after retry: no JSON object in response']
  - cited [update] We've recently released an update to fix this. We do recommend creating a current backup of the data on your device before updating. Here's more about the new update: <url> Let us know if this helps. <url>

## 2913270:A_v1  [passed]  intent=keyboard_text_bug level=STRONG
- customer: FIX THIS BUG. EVERYTIME I TYPE “it” IM AUTOCORRECTED TO “I.T” AND ITS ANNOYING.
- draft: We want to help with this! If you haven't yet, please back up your device and update to the latest version of iOS. iOS 11.1.1 was recently released and includes fixes for autocorrect issues like this one. Let us know if that helps!
- refs: ['2287602', '2312398']  issues: []
  - cited [update] Let's be sure we've got iOS 11.1.1 installed. It was released recently and includes some fixes for autocorrect issues. You can check that in Settings > General > About. If not, you can backup and install it now. How to back up: <url>
  - cited [update] We want to help you with this issue. If you haven’t yet, please back up your device and update it to the latest version iOS 11.1.1.

## 2913270:B_v2  [passed]  intent=keyboard_text_bug level=STRONG
- customer: FIX THIS BUG. EVERYTIME I TYPE “it” IM AUTOCORRECTED TO “I.T” AND ITS ANNOYING.
- draft: Let's be sure we've got iOS 11.1.1 installed. It was released recently and includes some fixes for autocorrect issues. You can check that in Settings > General > About. If not, you can back up and install it now using the steps on our support site.
- refs: ['2287602']  issues: []
  - cited [update] Let's be sure we've got iOS 11.1.1 installed. It was released recently and includes some fixes for autocorrect issues. You can check that in Settings > General > About. If not, you can backup and install it now. How to back up: <url>

## 506568:A_v1  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: Okay you fixed the problem with the “I” now do something about this it turning into I.T !!!!!!!
- draft: We'd like to look into this with you. Which device and software version are you currently using? You can check in Settings > General > About. Let us know and we'll go from there.
- refs: ['2492340']  issues: ['llm_support_check:You can check in Settings > General > About.']
  - cited [update] That issue has been fixed. If your I’s are still getting auto-corrected to question marks in a box when you type, that would mean you're still using an old version of software on your device. Get your device up to date in Settings > General > Software Update.

## 506568:B_v2  [passed]  intent=keyboard_text_bug level=STRONG
- customer: Okay you fixed the problem with the “I” now do something about this it turning into I.T !!!!!!!
- draft: We've recently released an update to address autocorrect issues. We recommend creating a current backup of your data before updating. Get your device up to date in Settings > General. Let us know if this helps!
- refs: ['2573954', '2492340']  issues: []
  - cited [update] We've recently released an update to fix this. We do recommend creating a current backup of the data on your device before updating. Here's more about the new update: <url> Let us know if this helps. <url>
  - cited [update] That issue has been fixed. If your I’s are still getting auto-corrected to question marks in a box when you type, that would mean you're still using an old version of software on your device. Get your device up to date in Settings > General > Software Update.

## 481855:A_v1  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: What’s with this I.T thing now come the fuck on
- draft: We'd love to help with this. Could you tell us more about what's happening with your keyboard? Are you seeing an unexpected autocorrect when typing the letter "I"?
- refs: ['1691799', '2573954', '2193441', '1585356', '1078794']  issues: ['evidence_coverage:coverage 0.14 < 0.25']
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>
  - cited [update] We've recently released an update to fix this. We do recommend creating a current backup of the data on your device before updating. Here's more about the new update: <url> Let us know if this helps. <url>
  - cited [update] Help is here to resolve that for you. We recently released an iOS update, 11.1.1, that contains a fix for autocorrect issues. Let’s be sure to back up your device prior to updating. How to back up: <url>
  - cited [update] Thanks for reaching out. This workaround will help until this issue is resolved in a future update: <url>
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url> <url>

## 481855:B_v2  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: What’s with this I.T thing now come the fuck on
- draft: We've recently released an update to fix this. We do recommend creating a current backup of your device before updating. You can find the steps on our support site. Let us know if this helps.
- refs: ['2573954']  issues: ['llm_support_check:You can find the steps on our support site.']
  - cited [update] We've recently released an update to fix this. We do recommend creating a current backup of the data on your device before updating. Here's more about the new update: <url> Let us know if this helps. <url>

## 599108:A_v1  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: Is anyone else having this problem with their iPhone and the word it becoming I.T.? I seriously don’t understand what ’s problem is with the letter I lately. <url>
- draft: We understand how frustrating that is! iOS 11.1.1 includes a fix for this autocorrect issue. Be sure to back up your device before updating, and let us know if the issue persists afterwards. Here's a workaround in the meantime: check your keyboard settings under Settings > Genera
- refs: ['1707789', '2485812', '1656582']  issues: ['llm_support_check:workaround: check your keyboard settings under Settings > General']
  - cited [update] Gotcha! Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>
  - cited [update] iOS 11.1.1 was recently released and it includes a fix for autocorrect issues. Be sure to back up your device prior to updating, and let us know if the issue persists afterwards. How to back up: <url> <url>
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>

## 599108:B_v2  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: Is anyone else having this problem with their iPhone and the word it becoming I.T.? I seriously don’t understand what ’s problem is with the letter I lately. <url>
- draft: None
- refs: []  issues: []

## 589479:A_v1  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: im tired of ya and these glitches now everytime I write it shit changes to I.t.... LIKE WHAT
- draft: We hear you, and we know autocorrect issues are frustrating. There's a workaround you can try until this is fixed in a future software update. DM us and we'll share the details.
- refs: ['1691799']  issues: ["llm_support_check:DM us and we'll share the details."]
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>

## 589479:B_v2  [passed]  intent=keyboard_text_bug level=STRONG
- customer: im tired of ya and these glitches now everytime I write it shit changes to I.t.... LIKE WHAT
- draft: Here's what you can do to work around the issue until it's fixed in a future software update: the steps on our support site can help. We know this is frustrating and appreciate your patience!
- refs: ['1691799']  issues: []
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>

## 2910465:A_v1  [passed]  intent=keyboard_text_bug level=STRONG
- customer: Dear Why, oh, can’t eye type the letter eye? It’s driving me mad. Please SOS #I️ #aBOX
- draft: We hear you! Here's what you can do to work around the issue until it's fixed in a future software update. We appreciate your patience!
- refs: ['2116235']  issues: []
  - cited [update] Here’s what you can do to work around the issue until it’s fixed in a future software update: <url>

## 2977723:A_v1  [BLOCKED]  intent=keyboard_text_bug level=STRONG
- customer: Yo, , my keyboard is once again replacing “it” with I.T. Your fix for this didn’t last long.
- draft: We'd love to help with that autocorrect issue. Could you let us know which device and software version you're using? That'll help us point you to the right fix.
- refs: []  issues: ['evidence_refs:no valid evidence references']
