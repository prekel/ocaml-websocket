open Lwt.Infix

let main port =
  let module W = Websocket_lwt_unix in
  let endpoint = `TCP (`IP (Ipaddr.of_string_exn "127.0.0.1"), `Port port) in
  let uri = Uri.of_string (Printf.sprintf "http://127.0.0.1:%d/" port) in
  (* Deterministic handshake nonce and masking bytes for this test only. *)
  W.connect ~random_string:(fun length -> String.make length 'B') endpoint uri >>= fun conn ->
  let pending = W.read conn in
  assert (Lwt.is_sleeping pending);
  Lwt.cancel pending;
  Lwt.catch (fun () -> pending >>= fun _ -> Lwt.fail_with "read was not canceled")
    (function Lwt.Canceled -> Lwt.return_unit | exn -> Lwt.fail exn)
  >>= fun () ->
  let send content =
    W.write conn (Websocket.Frame.create ~content ())
  in
  send "after-cancel" >>= fun () ->
  W.read conn >>= fun frame ->
  assert (frame.Websocket.Frame.content = "survived");
  send "ack" >>= fun () ->
  (* The peer half-closes its write side, but still accepts writes. *)
  Lwt.catch (fun () -> W.read conn >>= fun _ -> Lwt.fail_with "EOF expected")
    (function End_of_file -> Lwt.return_unit | exn -> Lwt.fail exn)
  >>= fun () ->
  Lwt.pause () >>= fun () ->
  Lwt.catch (fun () -> W.read conn >>= fun _ -> Lwt.fail_with "read failure expected")
    (function End_of_file | Lwt_io.Channel_closed _ -> Lwt.return_unit | exn -> Lwt.fail exn)
  >>= fun () ->
  W.close_transport conn >>= fun () ->
  (* The harness acknowledges only after the peer sees our transport close.
     Waiting here prevents process exit from masking a missing cleanup. *)
  Lwt_io.read_line Lwt_io.stdin >>= fun confirmation ->
  assert (confirmation = "closed");
  print_endline "Canceled read preserved connection; EOF propagated; explicit close succeeded";
  Lwt.return_unit

let () =
  Lwt_main.run (Lwt_unix.with_timeout 10. (fun () -> main (int_of_string Sys.argv.(1))))
