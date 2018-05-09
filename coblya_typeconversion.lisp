;; create a Maxima list object from the lisp cons list
;; this is the "undo" to https://github.com/andrejv/maxima/blob/master/share/cobyla/cobyla-interface.lisp
;; call in Maxima using 
;; 		[fitres, fiterr, niter, retncode] : fmin_cobyla(z, vars, ic, constraints)
;; 		coblya_result_to_maxima(fitres);
;;
;; alternatively (requires its own cell):
;; :lisp (setq $maximafitres (list\* '(mlist) (mapcar (lambda (x) (caddr x)) (cdr $fitres))))
;;
(defun $%coblya_result_to_maxima (eqlist)	
	(list\* '(mlist) (mapcar (lambda (x) (caddr x)) (cdr eqlist)))
)