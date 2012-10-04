/* 
 * File:   MyFrame.h
 * Author: a22543
 *
 * Created on October 1, 2012, 3:23 PM
 */

#ifndef MYFRAME_H
#define	MYFRAME_H

#include "MyMpWindow.h"
#ifdef __WXMSW__
#include "wxMemoryMappedFile.h"
#else
#include <sys/mman.h>
#endif

class MyFrame : public wxFrame
{
public:
    MyFrame();
    virtual ~MyFrame();
    void OnOpen(wxCommandEvent& event);
    void OnStartDraw(wxCommandEvent& event);
    void OnToggle1(wxCommandEvent& event);
    void OnToggle2(wxCommandEvent& event);
    void updateStatusText(wxString str);
    void stats();
#ifdef __WXMSW__
	wxMemoryMappedFile * m_x;
	wxMemoryMappedFile * m_y1;
	wxMemoryMappedFile * m_y2;
#else
    int m_xfd;
    int m_y1fd;
    int m_y2fd;
#endif
    unsigned int * m_xmap;
    unsigned int * m_ymap;
    unsigned int * m_y1map;
    double m_cur1x;
    double m_cur2x;
    int record_count;
    MyMpWindow * m_plot1;
    MyMpWindow * m_plot2;
    MyMpWindow * m_plot3;
    MyMpWindow * m_plot4;
    MyMpWindow * m_plot5;
    MyMpWindow * m_plot6;
    wxTextCtrl * m_log;
    void move_cur1(double x);
    void move_cur2(double x);
    DECLARE_EVENT_TABLE()
};

#endif	/* MYFRAME_H */

