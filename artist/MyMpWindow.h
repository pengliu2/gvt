/* 
 * File:   MyMpWindow.h
 * Author: a22543
 *
 * Created on October 1, 2012, 11:30 AM
 */

#ifndef MYMPWINDOW_H
#define	MYMPWINDOW_H

#include <wx/wx.h>
#include "mathplot.h"
#include "MyCursor.h"

class MyCurve : public mpFXY
{
    unsigned int * all_mem;
    unsigned int * x_mem;
    unsigned int * y_mem;
    int offset;
    int count;
    int column_offset;
public:
    MyCurve(unsigned int * x, unsigned int * y, int c, wxString name)
    :mpFXY( name )
    {
        x_mem = x;
        y_mem = y;
        count = c;
        offset = 0;
        m_drawOutsideMargins = false;
    }
    MyCurve(unsigned int *x, int c, wxString name, int offset)
    {
        all_mem = x;
        count = c;
        offset = 0;
        column_offset = offset;
    }
    virtual bool GetNextXY(double & x, double & y)
    {
        if (offset < count){
            x = x_mem[offset];
            y = y_mem[offset];
            offset++;
            return TRUE;
        } else {
            return FALSE;
        }
    }
    virtual void Rewind()
    {
        offset = 0;
    }
    virtual double GetMaxX() { return 2147483647; }
    virtual double GetMinX() { return 0; }
    virtual double GetMaxY() { return 1024; }
    virtual double GetMinY() { return 0; }
};

class MyEvent : public mpFXY
{
    unsigned int * x_mem;
    unsigned int * y_mem;
    int offset;
    int count;
    int candidate_y;
    int max;
public:
    MyEvent(unsigned int * x, unsigned int * y, int c, wxString name, double max_y)
    :mpFXY( name )
    {
        candidate_y = -1;
        x_mem = x;
        y_mem = y;
        count = c;
        offset = 0;
        m_drawOutsideMargins = false;
        max = (int)(max_y/2);
    }
    virtual bool GetNextXY(double & x, double & y)
    {
        if (offset < count){
            x = x_mem[offset];
            y = y_mem[offset];
            if (candidate_y < 0){
                offset++;
                candidate_y = y;
            } else if (candidate_y == y){
                    offset++;
            } else {
                y = candidate_y;
                candidate_y = y_mem[offset];
            }
            y = y * max;
            return TRUE;
        } else {
            return FALSE;
        }
    }
    virtual void Rewind()
    {
        offset = 0;
        candidate_y = -1;
    }
    virtual double GetMaxX() { return 2147483647; }
    virtual double GetMinX() { return 0; }
    virtual double GetMaxY() { return max; }
    virtual double GetMinY() { return 0; }
};

/*
MyPercent : public mpFXY
{
    
};
*/

class MyMpWindow : public mpWindow
{
    bool m_moving_cursor1;
    bool m_moving_cursor2;
    bool m_cross_cursor1;
    bool m_cross_cursor2;
    MyCursor *m_cur1;
    MyCursor *m_cur2;
public:
    MyMpWindow() {}
    MyMpWindow( wxWindow *parent, wxWindowID id, const wxPoint &pos, const wxSize &size, long flag );
    MyCursor *m_cur1_layer;
    MyCursor *m_cur2_layer;
    void move_cur1(double x);
    void move_cur2(double x);
    void StartDraw(unsigned int *x, unsigned int *y, unsigned int *y1);
    //void StartDraw(MyFrame::Curve *curves, int count);
protected:
    void OnMouseRightDown(wxMouseEvent     &event);
    void OnMouseRightUp(wxMouseEvent &event);
    void OnMouseMove(wxMouseEvent &event);
    void OnMouseLeftDown(wxMouseEvent &event);
    void OnMouseLeftRelease(wxMouseEvent &event);
    DECLARE_DYNAMIC_CLASS(mpWindow)
    DECLARE_EVENT_TABLE()
};

#endif	/* MYMPWINDOW_H */

